# llm-primitives-stgp

Research code for a journal paper on **LLM-authored primitives for strongly typed genetic programming (STGP) in trading**. Can an LLM author and maintain the primitive set of an STGP, using mathematics from outside finance (information theory, information geometry, optimal transport, rough paths, fractal analysis, statistical physics, spectral methods), to induce per-asset entry/exit trading rules? Here *operators* means functions in the GP function set, not genetic operators.

The research plan and literature survey live in the project folder, not in this repository.

## Status

Work package 1 (library, data layer and harness) is in progress. No LLM calls are made in WP1.

## Layout

```
config/            experiment settings and the Tier A universe; machine paths in paths.toml (git-ignored)
docs/              decisions log, generated operator catalogue, arm-6 review checklist
scripts/           data download/build, reports, smoke test, projections, repository hygiene
src/lpstgp/
  data/            schema, raw-file manifest, horizon-enforcing store, tier loaders, data quality
  splits.py        walk-forward periods; sandbox.py: leakage-safe data access
  types.py         semantic types (Series, Path, Hist, Real, Bool, Regime) and parameter kinds
  operators/       operator contract, registry and version lock; one file per operator version
    core/          histogram/path constructors, adaptive thresholds, comparators, logic, regimes
    <domain>/      seed library, about 4 operators per mathematical domain
    conventional/  technical-analysis and directional-change terminals (separate module)
  gates/           admission checks shared with the later maintenance loop
  backtest/        vectorised long-only backtester, costs, metrics
  gp/              DEAP-based STGP: primitive set, generation, variation, evaluation, fitness, runs
tests/             unit, gates, reference-implementation, leakage, data and GP tests
```

## Setup

```sh
brew install uv                    # or see https://docs.astral.sh/uv/
uv sync --all-extras               # Python 3.12, runtime + dev + reference-test dependencies
cp config/paths.example.toml config/paths.toml   # then edit the paths
git config core.hooksPath .githooks              # enable the hygiene pre-commit hook
```

## Tests

```sh
uv run pytest                      # everything, including tests on local real data
uv run pytest -m "not realdata"    # what CI runs (synthetic data only)
uv run ruff check . && uv run ruff format --check .
```

## Data and leakage rules

- Raw data, results, caches and secrets are never committed (enforced by `.gitignore` and `scripts/check_hygiene.py`).
- Data paths come from `config/paths.toml`; nothing is hard-coded.
- Test-period data are unreachable from operators and GP fitness: all modelling code receives a horizon-truncated sandbox, and this is enforced by tests.
- Every design choice is recorded in `docs/decisions.md`.
