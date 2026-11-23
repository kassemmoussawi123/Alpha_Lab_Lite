# AlphaLabLite

**A verifiable research loop for time-series experiments.**

AlphaLabLite turns structured strategy proposals into executable experiments.
It validates proposals, builds scripts in a small domain-specific language
(DSL), checks strategy similarity and complexity, runs cost-aware simulations,
and saves reproducible experiment records.

The research loop is inspired by R&D-Agent-Quant. It combines software
engineering, controlled LLM integration, and quantitative experiment evaluation.

## Features

- **Research loop:** propose parameters, validate, execute, evaluate, and use
  validation feedback to guide the next experiment.
- **Strategy similarity checks:** canonical expression trees ignore intermediate
  variable names. A configurable heuristic combines tree structure and numeric
  parameter similarity to reject duplicates and very small variations.
- **Complexity limits:** bound command count, expanded expression-node count,
  and dependency depth before execution.
- **Controlled execution:** only registered DSL operations can run; proposals
  cannot supply Python or shell commands.
- **Cost-aware simulation:** next-bar execution, long-only cash-limited positions,
  transaction fees, slippage, and final liquidation costs.
- **Chronological evaluation:** select on the first 70% of observations and
  evaluate the chosen strategy on the remaining 30%.
- **Reproducible history:** SQLite records include hypotheses, scripts, validation
  metrics, strategy checks, holdout results, trades, and source/data hashes.
- **CLI and REST API:** run experiments, analyze strategies, and retrieve
  outputs from the original scripting engine.

## Quick start

Requires Python 3.11 or later. Run these commands from the project directory:

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Then install dependencies, run tests, and run the offline demonstration:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python research.py --mode offline --rounds 3
```

The demo writes `research_report.json` and stores the full report in
`research_runs.db`. Offline mode uses deterministic feedback-guided parameter
search and requires no model credentials.

### Optional LLM proposals

LLM mode uses an OpenAI-compatible HTTPS chat-completions endpoint. Set these
environment variables locally:

| Variable | Purpose |
| --- | --- |
| ALPHALAB_API_KEY | Your provider API key |
| ALPHALAB_MODEL | A model supported by that provider |
| ALPHALAB_API_BASE | Optional API base URL; defaults to https://api.openai.com/v1 |

```bash
python research.py --mode llm --rounds 3 --goal "Compare moving-average crossover strategies after costs"
```

The model proposes an EMA smoothing parameter, an SMA window, and a hypothesis.
The engine builds the executable script. Proposal retries receive validation
errors and previous validation summaries. The holdout segment is excluded
from model feedback. Each round allows at most two attempts; provider transport
failures stop execution.

The current research search space is EMA/SMA crossover strategies. The DSL
analyzer also supports rate-of-change and constant-series expressions.

## API

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open [interactive API documentation](http://127.0.0.1:8000/docs).

| Endpoint | Purpose |
| --- | --- |
| POST /research | Run 1–6 offline research rounds |
| POST /analyze | Check a strategy's complexity and similarity without execution |
| POST /execute | Execute a DSL script and save its variables |
| GET /view/{script_id}?items=price&items=fast | Retrieve saved variables |

Example request for `POST /research`:

```json
{"dataset":"OneMinuteGoldPrices","rounds":3}
```

For `POST /analyze`, provide `script` and optionally `previous_scripts`.
An accepted strategy returns node/depth metrics, a fingerprint, a canonical
expression tree, and maximum similarity. A rejected strategy returns HTTP 422.

LLM execution is available through the CLI, where provider use is explicit.

## DSL example

Each command has the form `variable = Function{configs}{inputs}`:

```text
price = Fetch{OneMinuteGoldPrices}{}
fast = ExponentialMovingAverage{0.3}{price}
slow = SimpleMovingAverage{20}{price}
entry = CrossAbove{}{fast, slow}
exit = CrossAbove{}{slow, fast}
```

Run the included script:

```bash
python main.py execute examples/crossover.dsl
python main.py view --id YOUR_SCRIPT_ID price fast slow
```

The research analyzer receives `price` as an existing input, so its scripts
start with the indicator commands rather than `Fetch`.

## Project structure

| File | Responsibility |
| --- | --- |
| parsing.py | Parse DSL commands |
| engine.py | Validate and dispatch registered operations |
| transformations.py | Fetch data and compute time-series transformations |
| strategy_checks.py | Build canonical expression trees; check similarity and complexity |
| research.py | Proposals, simulation, evaluation, and research history |
| storage.py | Persist and retrieve original DSL execution outputs |
| app.py | FastAPI endpoints |
| tests/ | Numerical, validation, feedback, and reproducibility tests |

The [original walkthrough notebook](AlphaLabLite_Walkthrough.ipynb) explains
the initial DSL engine. The research extension is documented here.

## Evaluation and limitations

The bundled dataset is a small demonstration dataset without timestamps.
Metrics include net return, maximum drawdown, trade count, and ending equity,
with a costed buy-and-hold baseline. Annualized metrics are omitted.

Indicators restart separately in validation and holdout segments. A strategy
may make no trades; its zero return is reported directly. Selection maximizes
validation net return, which can favor staying in cash. Repeated validation
search can overfit, and repeatedly inspecting holdout results can compromise
their independence. Broader research needs additional timestamped datasets and
a separately reserved final evaluation period.

Similarity is a syntax-and-parameter heuristic, not proof of originality or
semantic equivalence. Complexity checks measure expression size and depth.
These mechanisms are inspired by published work, with a smaller scope.

The original `PortfolioSimulation` DSL operation is retained for compatibility.
The research loop uses the separate cost-aware simulator in `research.py`.

**Verification:** the offline CLI, HTTP endpoints, and automated tests have
been exercised. The LLM adapter has mocked-response coverage; a live provider
run requires credentials and remains unverified.

## Project summary

AlphaLabLite extends a Python time-series DSL with a bounded research workflow.
It combines structured proposal validation, expression-tree similarity and
complexity checks, feedback-guided experiment search, chronological holdout
evaluation, cost-aware simulation, and reproducible SQLite records. A FastAPI
interface and an optional LLM proposal adapter expose the workflow.

## Related work

- [R&D-Agent-Quant](https://arxiv.org/abs/2505.15155): inspiration for the iterative
  research, development, execution, and feedback workflow.
- [AlphaAgent](https://arxiv.org/abs/2502.16789): inspiration for expression-based
  similarity and complexity controls.
- [Qlib](https://github.com/microsoft/qlib): a broader quantitative research
  platform and reference for organizing experiments and evaluation.

AlphaLabLite is an independent implementation. It does not depend on Qlib or
reproduce these systems' reported results.
