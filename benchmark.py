"""Controlled synthetic comparison, not evidence of real-market trading skill."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from quant import DEFAULT_CANDIDATES, audit, segment_result

SCENARIOS = ("trend", "range", "volatility_shift", "shock")
SEEDS = (11, 23, 37)


def synthetic_prices(scenario, seed, n=600):
    if scenario not in SCENARIOS or n < 100:
        raise ValueError("Use a supported scenario and at least 100 observations")
    rng = random.Random(seed)
    prices, log_price = [100.0], math.log(100)
    for i in range(1,n):
        if scenario == "range":
            log_price = math.log(100)+.03*math.sin(i*.18)+rng.gauss(0,.001)
        else:
            mu, sigma = .0006, .004
            if scenario == "volatility_shift":
                mu, sigma = .0001, (.001 if i < n//2 else .012)
            if scenario == "shock":
                mu, sigma = .0004, .003
            log_price += mu+rng.gauss(0,sigma)
            if scenario == "shock" and i == int(.85*n):
                log_price -= .15
        prices.append(math.exp(log_price))
    return prices


def random_candidates(seed, count=6):
    """Candidates are generated without inspecting prices or returns."""
    rng = random.Random(seed)
    return [{"alpha":round(rng.uniform(.1,.8),4),"window":rng.randint(5,40),
             "hypothesis":"Ex-ante random-search comparison"} for _ in range(count)]


def benchmark(seeds=SEEDS, n=600):
    rows = []
    for scenario in SCENARIOS:
        for seed in seeds:
            prices = synthetic_prices(scenario,seed,n)
            original = audit(prices,candidates=DEFAULT_CANDIDATES,label=scenario)
            random_search = audit(prices,candidates=random_candidates(seed),label=scenario)
            boundary = int(.8*n)
            fixed = segment_result(DEFAULT_CANDIDATES[0],prices,boundary,n,10,5)
            strategies = {
                "preset_search":original["holdout"],
                "equal_budget_random_search":random_search["holdout"],
                "fixed_ema_sma":fixed,
                "buy_and_hold":original["holdout_baseline"],
                "cash":{"net_return":0.0,"max_drawdown":0.0,"trade_count":0}}
            rows.append({"scenario":scenario,"seed":seed,
                         "data_sha256":original["data_sha256"],
                         "holdout_range":[boundary,n],
                         "strategies":{name:{k:r[k] for k in ("net_return","max_drawdown","trade_count")}
                                       for name,r in strategies.items()}})
    summary = {}
    for name in rows[0]["strategies"]:
        values = [row["strategies"][name] for row in rows]
        summary[name] = {"mean_holdout_return":statistics.mean(v["net_return"] for v in values),
                         "median_holdout_return":statistics.median(v["net_return"] for v in values),
                         "mean_holdout_drawdown":statistics.mean(v["max_drawdown"] for v in values),
                         "no_trade_cases":sum(v["trade_count"]==0 for v in values)}
    return {"benchmark_version":1,"scenario_type":"synthetic_controlled",
            "case_count":len(rows),"bars_per_case":n,"seeds":list(seeds),
            "candidate_budget":{"preset_search":6,"equal_budget_random_search":6},
            "costs":{"fee_bps":10,"slippage_bps":5},"final_holdout_fraction":.2,
            "source_sha256":hashlib.sha256(b"".join((Path(__file__).parent/name).read_bytes() for name in
                ("benchmark.py","quant.py","research.py","engine.py","parsing.py","transformations.py"))).hexdigest(),
            "rows":rows,"summary":summary,
            "interpretation":"Controlled software comparison only. Synthetic outcomes do not establish real-market alpha or AI superiority.",
            "method_notes":["Candidate sets and scenario seeds are fixed before evaluation.",
               "Both search methods use identical selection, costs, and data splits.",
               "Final holdout returns are not used to select parameters.",
               "Cases are small and engineered; no statistical significance is claimed.",
               "The optional LLM is not used or evaluated by this benchmark."]}


def markdown(result):
    lines = ["# Controlled benchmark", "", result["interpretation"], "",
             f"{result['case_count']} cases: four synthetic scenarios, {len(result['seeds'])} seeds, {result['bars_per_case']} bars per case.",
             "Preset and random search each receive six candidate evaluations per selection step.",
             "10 bps fees and 5 bps slippage; final 20% holdout.", "",
             "| Method | Mean holdout return | Mean drawdown | No-trade cases |",
             "| --- | ---: | ---: | ---: |"]
    for name,r in result["summary"].items():
        lines.append(f"| {name} | {r['mean_holdout_return']:.2%} | {r['mean_holdout_drawdown']:.2%} | {r['no_trade_cases']} |")
    lines += ["", "## Protocol", ""]+["- "+x for x in result["method_notes"]]
    lines += ["", "Reproduce: `python benchmark.py --out benchmark_results.json --markdown docs/BENCHMARK.md`", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",default="benchmark_results.json")
    parser.add_argument("--markdown",default="docs/BENCHMARK.md")
    args = parser.parse_args()
    result = benchmark()
    Path(args.out).write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    target = Path(args.markdown)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(markdown(result),encoding="utf-8")
    print(json.dumps({"cases":result["case_count"],"summary":result["summary"]},indent=2))


if __name__ == "__main__":
    main()
