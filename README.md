# llm-primitives-stgp

Research code for a journal paper on **LLM-authored primitives for strongly typed genetic programming (STGP) in trading**. Can an LLM author and maintain the primitive set of an STGP, using mathematics from outside finance (information theory, information geometry, optimal transport, rough paths, fractal analysis, statistical physics, spectral methods), to induce per-asset entry/exit trading rules? Here *operators* means functions in the GP function set, not genetic operators.

The research plan and literature survey live in the project folder, not in this repository.

## Status

**Work package 1 (library, data layer and harness) is complete.** No LLM calls are made in WP1. The seed library is the hand-specified "expert" control (arm 6; see `docs/decisions.md`, D-002).

| Component | What it is |
|---|---|
| Data layer | Schema v1 (raw prices + events, causal adjustment), Tier A pilot download with checksummed manifest, Tier B selection rule and loader interface, Tier C loader, data reports |
| Splits and leakage | 18 rolling walk-forward periods (fit 2 y + validation 1 y, test 1 y); `Sandbox` gives modelling code warm-up + data before the stage horizon only; test data are sealed |
| Operator library | 91 frozen, versioned contracts: 28 cross-domain operators (4 per domain), 17 core operators, 3 data terminals, 23 TA and 20 directional-change terminals (`docs/operators.md`) |
| Admission gates | compiles + source policy, type-correct, finite and non-constant (synthetic and real data), deterministic (also across processes), prefix-invariant, exact lookback, declared invariances, reference-implementation tests |
| STGP | DEAP typed primitive set; own lookback-aware generation, homologous crossover, mutation, selection; entry/exit rule pairs; robustness-composite fitness; reproducible runs |
| Backtester | long-only, one-bar execution shift, per-asset costs with a multiplier, batch mode |

## Layout

```
config/            settings.toml (splits, GP, fitness, quality), universe_tierA.toml; paths.toml (git-ignored)
docs/              decisions.md, operators.md (generated), arm6_review.md (review log)
scripts/           download_tier_a, build_data, data_reports, smoke_test, calibrate, project_compute,
                   generate_operator_docs, update_lock, check_hygiene
src/lpstgp/
  data/            schema, manifest, horizon-enforcing store, Tier A/B/C, data quality, pilot sources
  splits.py        walk-forward periods and eligibility; sandbox.py: leakage-safe data access
  types.py         semantic types (Series, Path, Hist, Real, Bool, Regime) and parameter grids
  operators/       contract, registry and version lock (registry.lock.toml); one file per operator version
    core/          histogram/path constructors, adaptive thresholds, comparators, Kleene logic, regimes
    <domain>/      seed library, 4 operators per mathematical domain
    conventional/  technical-analysis and directional-change terminals (separate module)
  gates/           admission checks (shared with the WP3 maintenance loop), synthetic inputs, source policy
  backtest/        engine, costs, metrics
  gp/              primitive set, generation, variation, evaluation, fitness, run loop
  runner.py        sandboxes -> STGP run -> JSON run record (parallel runs in spawned workers)
tests/             data, leakage, operators (reference implementations), gates, backtest, gp
```

## Setup

```sh
brew install uv                                  # or see https://docs.astral.sh/uv/
uv sync --all-extras                             # uv-managed Python 3.12 + all dependencies (uv.lock)
cp config/paths.example.toml config/paths.toml   # then edit the four paths
git config core.hooksPath .githooks              # enable the hygiene pre-commit hook
```

## Typical commands

```sh
uv run python scripts/download_tier_a.py         # raw pilot data + manifest (free sources, pilot only)
uv run python scripts/build_data.py              # raw -> processed Parquet (offline, causal)
uv run python scripts/data_reports.py            # coverage/gap reports per tier -> reports_dir
uv run pytest                                    # all tests, incl. real-data gates when data are present
uv run pytest -m "not realdata"                  # what CI runs (synthetic data only, no network)
uv run python scripts/smoke_test.py              # STGP on 2 assets x P01, small budget
uv run python scripts/calibrate.py               # timings for the projections (training data only)
uv run python scripts/project_compute.py         # compute and disk projections -> reports_dir
uv run python scripts/generate_operator_docs.py  # regenerate docs/operators.md after adding an operator
uv run python scripts/update_lock.py             # lock new operator versions (locked ones are immutable)
```

## Data and leakage rules

- Raw data, results, caches and secrets are never committed (`.gitignore`, `scripts/check_hygiene.py` in the pre-commit hook and CI).
- Data paths come from `config/paths.toml` (or `$LPSTGP_PATHS`); nothing is hard-coded. Caches must live outside cloud-synced folders.
- Modelling code (operators, GP, backtest) cannot import the data layer or do I/O (static policy test). It only ever receives a `Sandbox`, whose arrays end before the stage horizon; the test stage is sealed. Canary tests poison all later rows and check that nothing changes.
- Every operator is prefix-invariant and has an exact, declared lookback (tested bit for bit), and every rule's lookback is capped at 504 bars.
- Every design choice is recorded in `docs/decisions.md`.

## Adding an operator

Add `src/lpstgp/operators/<domain>/<name>__v<n>.py` defining `SPEC = OperatorSpec(...)` with its definition, references and implementation; add a reference test; run the gate suite (`uv run pytest tests/gates tests/operators`), then `scripts/update_lock.py` and `scripts/generate_operator_docs.py`. A change to a locked operator must be a new version file.

## Licence

Not yet chosen (see `docs/decisions.md`, D-007). The repository is private until the licence is set.
