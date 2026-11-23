# Controlled benchmark

Controlled software comparison only. Synthetic outcomes do not establish real-market alpha or AI superiority.

12 cases: four synthetic scenarios, 3 seeds, 600 bars per case.
Preset and random search each receive six candidate evaluations per selection step.
10 bps fees and 5 bps slippage; final 20% holdout.

| Method | Mean holdout return | Mean drawdown | No-trade cases |
| --- | ---: | ---: | ---: |
| preset_search | 3.68% | 5.65% | 0 |
| equal_budget_random_search | 2.74% | 5.65% | 0 |
| fixed_ema_sma | 1.78% | 5.27% | 0 |
| buy_and_hold | 2.97% | 8.51% | 0 |
| cash | 0.00% | 0.00% | 12 |

## Protocol

- Candidate sets and scenario seeds are fixed before evaluation.
- Both search methods use identical selection, costs, and data splits.
- Final holdout returns are not used to select parameters.
- Cases are small and engineered; no statistical significance is claimed.
- The optional LLM is not used or evaluated by this benchmark.

Reproduce: `python benchmark.py --out benchmark_results.json --markdown docs/BENCHMARK.md`
