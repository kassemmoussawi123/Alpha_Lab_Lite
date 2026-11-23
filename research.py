"""Bounded research loop inspired by RD-Agent(Q), not a reproduction of it."""
import argparse
from contextlib import closing
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import urllib.request
import uuid

from engine import executeScript
from strategy_checks import check_strategy

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "fetch_transformation_data.csv"
SYSTEM = """You propose moving-average experiments using JSON only:
{"alpha":0.3,"window":20,"hypothesis":"short explanation"}.
alpha must be >0 and <=1; window integer 2..60. No code, tools, or extra keys.
Use previous validation feedback to choose a different candidate. Do not claim
profitability or access to test data. Return only the JSON object."""

def validate_proposal(p):
    if not isinstance(p, dict) or set(p) != {"alpha", "window", "hypothesis"}:
        raise ValueError("Proposal must contain alpha, window, hypothesis only")
    if isinstance(p["alpha"], bool) or not isinstance(p["alpha"], (int, float)) or not 0 < p["alpha"] <= 1:
        raise ValueError("alpha must be in (0,1]")
    if type(p["window"]) is not int or not 2 <= p["window"] <= 60:
        raise ValueError("window must be an integer from 2 to 60")
    if not isinstance(p["hypothesis"], str) or not 1 <= len(p["hypothesis"]) <= 1000:
        raise ValueError("hypothesis must have 1..1000 characters")
    return p

def propose(mode, feedback, attempt=0, goal="Compare moving-average strategies", errors=()):
    if mode == "offline":
        # Deterministic feedback-guided local search, not an LLM.
        candidates = [(0.3, 20), (0.15, 10), (0.5, 30), (0.7, 5), (0.1, 40), (0.4, 15)]
        seen = {(x["proposal"]["alpha"], x["proposal"]["window"]) for x in feedback}
        if feedback:
            best = max(feedback, key=lambda x: x["validation"]["net_return"])["proposal"]
            candidates.sort(key=lambda x: abs(x[0]-best["alpha"]) + abs(x[1]-best["window"])/60)
        a, w = next(x for x in candidates if x not in seen)
        return validate_proposal({"alpha":a, "window":w,
            "hypothesis":"Test whether a fast EMA crossing a slower SMA improves validation return after costs."})
    key = os.environ.get("ALPHALAB_API_KEY")
    model = os.environ.get("ALPHALAB_MODEL")
    if not key or not model:
        raise ValueError("LLM mode requires ALPHALAB_API_KEY and ALPHALAB_MODEL")
    base = os.environ.get("ALPHALAB_API_BASE", "https://api.openai.com/v1").rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("LLM endpoint must use HTTPS")
    payload = {"model":model, "messages":[{"role":"system","content":SYSTEM},
        {"role":"user","content":json.dumps({"goal":goal,"feedback":feedback,"attempt":attempt,"validation_errors":list(errors)[-2:]})}],
        "max_tokens":400}
    req = urllib.request.Request(base+"/chat/completions", data=json.dumps(payload).encode(),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("Model response too large")
    obj = json.loads(raw)["choices"][0]["message"]["content"]
    return validate_proposal(json.loads(obj))

def load_prices(label, path=DATA):
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if row and row[0] == label:
                values = [float(v) for v in row[1:] if v.strip()]
                if len(values) < 30 or any(not math.isfinite(v) or v <= 0 for v in values):
                    raise ValueError("Need at least 30 finite positive prices")
                return values
    raise ValueError("Unknown data label: "+label)

def script_for(p):
    validate_proposal(p)
    return ("fast = ExponentialMovingAverage{"+str(p["alpha"])+"}{price}\n"
        "slow = SimpleMovingAverage{"+str(p["window"])+"}{price}\n"
        "entry = CrossAbove{}{fast, slow}\nexit = CrossAbove{}{slow, fast}")

def simulate(prices, entry, exits, fee_bps=10, slippage_bps=5, initial=10000):
    if not prices or len(prices) != len(entry) or len(prices) != len(exits):
        raise ValueError("Prices and signals must have equal nonzero lengths")
    if fee_bps < 0 or slippage_bps < 0 or fee_bps >= 10000 or slippage_bps >= 10000:
        raise ValueError("Costs must be in [0,10000) bps")
    cash, units = initial, 0.0
    fee, slip = fee_bps/10000, slippage_bps/10000
    equity, trades = [], []
    for i, price in enumerate(prices):
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Prices must be finite and positive")
        # The signal at t-1 can only trade at t. Long-only, one position.
        if i and exits[i-1] and units:
            fill = price*(1-slip)
            cash += units*fill*(1-fee)
            trades.append({"bar":i,"side":"sell","fill":fill,"units":units})
            units = 0.0
        elif i and entry[i-1] and not units:
            fill = price*(1+slip)
            units = cash/(fill*(1+fee))
            cash = 0.0
            trades.append({"bar":i,"side":"buy","fill":fill,"units":units})
        equity.append(cash+units*price)
    # Liquidate at segment end, charging the same costs.
    if units:
        fill = prices[-1]*(1-slip)
        cash += units*fill*(1-fee)
        trades.append({"bar":len(prices)-1,"side":"sell_final","fill":fill,"units":units})
        equity[-1] = cash
    peak, drawdown = initial, 0.0
    for value in equity:
        peak = max(peak,value)
        drawdown = max(drawdown,1-value/peak)
    return {"net_return":equity[-1]/initial-1,"max_drawdown":drawdown,
            "trade_count":len(trades),"ending_equity":equity[-1],
            "equity":equity,"trades":trades}

def evaluate(p, prices, fee, slip):
    memory = executeScript(script_for(p), initial_memory={"price":prices})
    return simulate(prices,memory["entry"],memory["exit"],fee,slip)

def compact(result):
    return {k:v for k,v in result.items() if k not in ("equity","trades")}

def run(label="OneMinuteGoldPrices", rounds=3, mode="offline",
        db=None, fee=10, slip=5, goal="Compare moving-average strategies"):
    if mode not in ("offline","llm") or not 1 <= rounds <= 6:
        raise ValueError("Use offline/llm mode and 1..6 rounds")
    prices = load_prices(label)
    boundary = int(len(prices)*0.7)
    validation, test = prices[:boundary], prices[boundary:]
    if min(len(validation),len(test)) < 5:
        raise ValueError("Insufficient split sizes")
    # Frozen chronological holdout; test data never enters proposal feedback.
    feedback, failures = [], []
    for iteration in range(rounds):
        for attempt in range(2):
            try:
                p = propose(mode,feedback,attempt,goal,failures)
                if p["window"] >= len(validation):
                    raise ValueError("Window must be shorter than validation segment")
                if any((p["alpha"],p["window"]) == (x["proposal"]["alpha"],x["proposal"]["window"]) for x in feedback):
                    raise ValueError("Duplicate proposal")
                checks = check_strategy(script_for(p), [x["script"] for x in feedback])
                result = evaluate(p,validation,fee,slip)
                feedback.append({"iteration":iteration,"proposal":p,
                                 "validation":compact(result),"script":script_for(p),
                                 "strategy_checks":checks})
                break
            except (ValueError,KeyError,TypeError) as error:
                failures.append({"iteration":iteration,"attempt":attempt,"error":str(error)})
        else:
            raise ValueError("Proposal failed validation twice; experiment stopped")
    winner = max(feedback,key=lambda x:x["validation"]["net_return"])
    test_result = evaluate(winner["proposal"],test,fee,slip)
    buy = [1]+[0]*(len(test)-1)
    baseline = simulate(test,buy,[0]*len(test),fee,slip)
    try:
        revision = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,
            stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        revision = None
    report = {"run_id":str(uuid.uuid4()),"mode":mode,"goal":goal,
        "dataset":label,"data_sha256":hashlib.sha256(DATA.read_bytes()).hexdigest(),
        "code_revision":revision,"code_sha256":hashlib.sha256(b"".join(
            (ROOT/name).read_bytes() for name in ("research.py","engine.py","parsing.py","transformations.py","strategy_checks.py"))).hexdigest(),
        "split":{"validation_bars":len(validation),"test_bars":len(test),
                 "method":"70/30 chronological; indicators restart on each segment"},
        "costs":{"fee_bps":fee,"slippage_bps":slip},
        "experiments":feedback,"proposal_failures":failures,"selected":winner["proposal"],
        "test":test_result,"buy_and_hold":baseline,
        "limitations":["Small bundled dataset; no profitability claim.",
            "Repeated validation use can overfit; holdout is evaluated only after selection.",
            "No timestamps: annualized metrics are intentionally omitted.",
            "Offline mode is deterministic search, not an LLM agent."]}
    with closing(sqlite3.connect(db or ROOT/"research_runs.db")) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, report TEXT NOT NULL)")
        conn.execute("INSERT INTO research_runs VALUES (?,?)",
                     (report["run_id"],json.dumps(report,allow_nan=False)))
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=["offline","llm"],default="offline")
    parser.add_argument("--rounds",type=int,default=3)
    parser.add_argument("--dataset",default="OneMinuteGoldPrices")
    parser.add_argument("--db",default=str(ROOT/"research_runs.db"))
    parser.add_argument("--out",default=str(ROOT/"research_report.json"))
    parser.add_argument("--goal",default="Compare moving-average strategies")
    args = parser.parse_args()
    report = run(args.dataset,args.rounds,args.mode,args.db,goal=args.goal)
    Path(args.out).write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"run_id":report["run_id"],"mode":report["mode"],
        "test":compact(report["test"]),"baseline":compact(report["buy_and_hold"]),
        "report":args.out},indent=2))

if __name__ == "__main__":
    main()
