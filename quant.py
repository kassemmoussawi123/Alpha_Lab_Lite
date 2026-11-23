"""Trader research diagnostics. Historical evidence, not trading instructions."""
import argparse
from contextlib import closing
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics
import uuid

from engine import executeScript
from research import ROOT, load_prices, script_for, simulate, compact, validate_proposal

DEFAULT_CANDIDATES = [
    {"alpha": a, "window": w, "hypothesis": "EMA/SMA trend-following candidate"}
    for a, w in [(0.3, 20), (0.15, 10), (0.5, 30), (0.7, 5), (0.1, 40), (0.4, 15)]
]


def validate_prices(prices):
    if not 40 <= len(prices) <= 10000:
        raise ValueError("Provide 40..10000 ordered prices")
    if any(isinstance(v, bool) or not isinstance(v, (float, int))
           or not math.isfinite(v) or v <= 0 for v in prices):
        raise ValueError("Prices must be finite positive numbers")


def read_price_csv(path):
    """Strict timestamp,close input: reject missing bars, duplicates, disorder."""
    prices, timestamps = [], []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"timestamp", "close"} <= set(reader.fieldnames):
            raise ValueError("CSV requires timestamp and close columns")
        for row in reader:
            try:
                stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                price = float(row["close"])
                if timestamps and stamp <= timestamps[-1]:
                    raise ValueError("Timestamps must be unique and strictly increasing")
            except (TypeError, KeyError, ValueError) as error:
                raise ValueError("Invalid CSV timestamp/close or unordered timestamps") from error
            timestamps.append(stamp)
            prices.append(price)
    validate_prices(prices)
    return prices


def fold_ranges(n, splits=3, gap=1):
    """Expanding training sets, nonoverlapping tests; ranges are half open."""
    if type(splits) is not int or not 2 <= splits <= 5 or type(gap) is not int or not 0 <= gap <= 10:
        raise ValueError("Use 2..5 folds and a gap of 0..10 bars")
    size = n // (splits + 2)
    first_test = n - splits * size
    if size < 4 or first_test - gap < 10:
        raise ValueError("Insufficient observations for requested folds/gap")
    return [(first_test+i*size-gap, first_test+i*size, first_test+(i+1)*size)
            for i in range(splits)]


def regime(prices):
    """Past-only descriptive heuristic, not a forecast or learned classifier."""
    recent = prices[-21:]
    distance = sum(abs(b-a) for a, b in zip(recent, recent[1:]))
    efficiency = abs(recent[-1]-recent[0])/distance if distance else 0.0
    returns = [b/a-1 for a, b in zip(prices, prices[1:])]
    recent_vol = statistics.pstdev(returns[-20:]) if returns else 0.0
    full_vol = statistics.pstdev(returns) if returns else 0.0
    return {"trend": "trending" if efficiency >= .35 else "ranging",
            "volatility": "elevated" if full_vol and recent_vol > 1.5*full_vol else "normal",
            "efficiency_ratio": efficiency, "recent_bar_volatility": recent_vol}


def segment_result(proposal, prices, start, end, fee, slip, initial=10000, buy_hold=False):
    """Use only data up to end. Prior bars warm indicators; trading starts at start."""
    if start < 1 or end <= start or end > len(prices):
        raise ValueError("Invalid evaluation range")
    prefix = prices[:end]
    if buy_hold:
        entries, exits = [0]*len(prefix), [0]*len(prefix)
        entries[start-1] = 1
    else:
        memory = executeScript(script_for(proposal), {"price": prefix})
        entries, exits = memory["entry"], memory["exit"]
    # One preceding observation supplies the first executable signal. It carries
    # no position and does not contribute a return to the evaluation interval.
    result = simulate(prices[start-1:end], entries[start-1:end], exits[start-1:end],
                      fee, slip, initial)
    result["equity"] = result["equity"][1:]
    for trade in result["trades"]:
        trade["bar"] += start-1
    result["turnover"] = sum(t["units"]*t["fill"] for t in result["trades"])/initial
    return result


def select_candidate(candidates, prices, train_end, fee, slip, drawdown_weight):
    eligible = [p for p in candidates if p["window"] < train_end-1]
    if not eligible:
        raise ValueError("No candidate fits the available training history")
    ranked = []
    for p in eligible:
        result = segment_result(p, prices, 1, train_end, fee, slip)
        score = result["net_return"]-drawdown_weight*result["max_drawdown"]
        ranked.append({"proposal": p, "score": score, "training": compact(result)})
    return max(ranked, key=lambda x: x["score"]), ranked


def risk_summary(equity, initial=10000):
    previous, peak, max_dd = initial, initial, 0.0
    returns = []
    for value in equity:
        returns.append(value/previous-1)
        previous, peak = value, max(peak, value)
        max_dd = max(max_dd, 1-value/peak)
    ordered = sorted(returns)
    tail_n = max(1, math.ceil(.05*len(ordered)))
    volatility = statistics.pstdev(returns)
    return {"net_return":equity[-1]/initial-1, "max_drawdown":max_dd,
            "bar_volatility":volatility,
            "return_to_volatility_per_bar":statistics.mean(returns)/volatility if volatility else None,
            "historical_expected_shortfall_95_per_bar":max(0, -statistics.mean(ordered[:tail_n])),
            "observations":len(equity)}


def audit(prices, candidates=None, splits=3, gap=1, fee=10, slip=5,
          drawdown_weight=.5, label="custom", db=None):
    validate_prices(prices)
    for value in (fee, slip, drawdown_weight):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Costs and drawdown weight must be finite nonnegative numbers")
    if fee >= 2500 or slip >= 2500 or drawdown_weight > 10:
        raise ValueError("Costs must be below 2500 bps; drawdown weight at most 10")
    candidates = list(DEFAULT_CANDIDATES if candidates is None else candidates)
    if not 1 <= len(candidates) <= 12:
        raise ValueError("Provide 1..12 candidates fixed before evaluation")
    for p in candidates:
        validate_proposal(p)
    # Keep the final 20% out of ALL diagnostics and parameter/cost exploration.
    development_end = int(len(prices)*.8)
    development = prices[:development_end]
    folds, path, baseline_path = [], [], []
    capital, baseline_capital = 10000.0, 10000.0
    for train_end, test_start, test_end in fold_ranges(len(development), splits, gap):
        winner, _ = select_candidate(candidates, development, train_end, fee, slip, drawdown_weight)
        chosen = winner["proposal"]
        result = segment_result(chosen, development, test_start, test_end, fee, slip, capital)
        baseline = segment_result(chosen, development, test_start, test_end, fee, slip,
                                  baseline_capital, buy_hold=True)
        path.extend(result["equity"])
        baseline_path.extend(baseline["equity"])
        capital, baseline_capital = result["ending_equity"], baseline["ending_equity"]
        folds.append({"train_range":[0,train_end], "test_range":[test_start,test_end],
                      "regime_from_training":regime(development[:train_end]),
                      "selected":chosen, "training_score":winner["score"],
                      "test":compact(result), "baseline":compact(baseline)})
    winner, rankings = select_candidate(candidates, development, len(development), fee, slip, drawdown_weight)
    selected = winner["proposal"]
    cost_scenarios = []
    for multiplier in (1, 2, 4):
        # Cap scenario costs below 100%; avoid NaN or invalid fills.
        f, s = fee*multiplier, slip*multiplier
        result = segment_result(selected, development, 1, len(development), f, s)
        cost_scenarios.append({"multiplier":multiplier, "fee_bps":f,
                               "slippage_bps":s, **compact(result)})
    neighborhood = []
    for da, dw in ((-.2, 0),(.2, 0),(0,-.2),(0,.2)):
        neighbor = dict(selected, alpha=min(1, max(.01,selected["alpha"]*(1+da))),
                        window=min(60,max(2,round(selected["window"]*(1+dw)))))
        result = segment_result(neighbor, development, 1, len(development), fee, slip)
        neighborhood.append({"alpha":neighbor["alpha"],"window":neighbor["window"],**compact(result)})
    # Select once on development history, then evaluate the frozen final segment.
    holdout = segment_result(selected, prices, development_end, len(prices), fee, slip)
    holdout_baseline = segment_result(selected, prices, development_end, len(prices), fee, slip,buy_hold=True)
    warnings = ["Small historical sample; findings are research diagnostics, not a live trading recommendation."]
    trade_count = sum(f["test"]["trade_count"] for f in folds)
    if trade_count < 6:
        warnings.append("Fewer than six walk-forward fills: insufficient trade evidence.")
    if holdout["trade_count"] == 0:
        warnings.append("Selected strategy made no holdout trades; a zero return is a cash outcome.")
    if cost_scenarios[0]["net_return"] > 0 >= cost_scenarios[-1]["net_return"]:
        warnings.append("Development profitability disappears under the 4x cost scenario.")
    local_returns = [p["net_return"] for p in neighborhood]
    if winner["training"]["net_return"] > 0 and min(local_returns) <= 0:
        warnings.append("At least one nearby parameter choice loses money on development history.")
    by_regime = {}
    for name in ("trending","ranging"):
        subset = [f for f in folds if f["regime_from_training"]["trend"] == name]
        by_regime[name] = {"fold_count":len(subset),"mean_fold_return":
                          statistics.mean(f["test"]["net_return"] for f in subset) if subset else None}
    report = {"run_id":str(uuid.uuid4()),"dataset":label,"bars":len(prices),
              "data_sha256":hashlib.sha256(json.dumps(prices,allow_nan=False).encode()).hexdigest(),
              "source_sha256":hashlib.sha256(b"".join((ROOT/n).read_bytes() for n in
                    ("quant.py","research.py","engine.py","parsing.py","transformations.py"))).hexdigest(),
              "selection_rule":{"formula":"training_net_return - weight * training_max_drawdown",
                                "drawdown_weight":drawdown_weight,"candidate_count":len(candidates)},
              "development_range":[0,development_end],"holdout_range":[development_end,len(prices)],
              "gap":gap,"walk_forward":folds,"walk_forward_risk":risk_summary(path),
              "walk_forward_baseline_risk":risk_summary(baseline_path),"regime_breakdown":by_regime,
              "selected":selected,"development_rankings":rankings,"cost_stress":cost_scenarios,
              "parameter_neighbors":neighborhood,"holdout":holdout,
              "holdout_baseline":holdout_baseline,"warnings":warnings,
              "method_notes":["Candidate set is fixed before folds; select using past training data only.",
                 "Indicators use preceding prices for warm-up; positions reset and liquidate per fold.",
                 "Gap excludes bars from parameter selection; known pre-test prices can warm indicators.",
                 "Regime labels are descriptive training-only heuristics, not predictions.",
                 "Stress and neighbor checks use development data only; holdout is not used for tuning.",
                 "Per-bar risk metrics are unannualized; short samples are not calibrated risk forecasts.",
                 "Candidate/model design informed by future data can invalidate this evaluation."]}
    total = sum(f["test"]["net_return"] > 0 for f in folds)
    report["research_note"] = (f"{total}/{len(folds)} walk-forward segments had positive net return; "
        f"{trade_count} fills were recorded. Review the cost stress, parameter neighborhood, "
        "and held-out trade count before considering a separate paper-trading study.")
    if db:
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS quant_audits (id TEXT PRIMARY KEY, report TEXT NOT NULL)")
            conn.execute("INSERT INTO quant_audits VALUES (?,?)",(report["run_id"],json.dumps(report,allow_nan=False)))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset",default="OneMinuteGoldPrices")
    parser.add_argument("--csv",help="CSV with strictly ordered ISO timestamp,close columns")
    parser.add_argument("--fee-bps",type=float,default=10)
    parser.add_argument("--slippage-bps",type=float,default=5)
    parser.add_argument("--splits",type=int,default=3)
    parser.add_argument("--gap",type=int,default=1)
    parser.add_argument("--out",default="quant_report.json")
    parser.add_argument("--html",help="Optional portable HTML evidence report")
    parser.add_argument("--db",default=str(ROOT/"research_runs.db"))
    args = parser.parse_args()
    prices = read_price_csv(args.csv) if args.csv else load_prices(args.dataset)
    result = audit(prices,splits=args.splits,gap=args.gap,fee=args.fee_bps,
                   slip=args.slippage_bps,label=Path(args.csv).name if args.csv else args.dataset,db=args.db)
    Path(args.out).write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    if args.html:
        from quant_report import render
        Path(args.html).write_text(render(result),encoding="utf-8")
    print(json.dumps({"report":args.out,"research_note":result["research_note"],
                      "warnings":result["warnings"]},indent=2))


if __name__ == "__main__":
    main()
