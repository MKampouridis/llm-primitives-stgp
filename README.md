# llm-primitives-stgp

Research code for a journal paper on **LLM-authored primitives for strongly typed genetic programming (STGP) in trading**. Can an LLM author and maintain the primitive set of an STGP, using mathematics from outside finance (information theory, information geometry, optimal transport, rough paths, fractal analysis, statistical physics, spectral methods), to induce per-asset entry/exit trading rules? Here *operators* means functions in the GP function set, not genetic operators.

This folder is the project's single location: code, the research plan (`docs/research_plan.md`), the literature survey (`docs/survey.md`, working notes in `docs/survey/`), decisions and generated reports are tracked; data, results and caches sit in git-ignored folders beside them. A one-way backup of docs, reports, results and raw data goes to Box (`scripts/backup.py`). Standing rules for coding sessions are in `CLAUDE.md`.

## Status

**Work package 1 (library, data layer and harness) is complete.** The seed library is the hand-specified "expert" control (arm 6; see `docs/decisions.md`, D-002).

**Work package 2 (whole LLM strategies, STGP arms 1–2, pilot go/no-go) is in progress.** The protocol is `docs/protocol.md`; decisions D-034–D-040. WP2 reads no data on or after 2008-07-01 (enforced in code); the pilot periods PL1/PL2 precede the 18 primary periods.

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
CLAUDE.md          standing project rules for Claude Code sessions
config/            settings.toml (splits, GP, fitness, quality), universe_tierA.toml; paths.toml (git-ignored)
docs/              research_plan.md, survey.md (+ survey/ working notes), decisions.md,
                   operators.md (generated), arm6_review.md (review log)
reports/<wp>/      generated reports (data, smoke test, projections, summaries)
data/              tierA/B/C raw downloads, manifests, processed Parquet       (git-ignored)
results/           per-run JSON records                                        (git-ignored)
cache/             disposable caches                                           (git-ignored)
scripts/           download_tier_a, build_data, data_reports, smoke_test, calibrate, project_compute,
                   generate_operator_docs, update_lock, check_hygiene, backup
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
  strategies/      WP2 whole strategies: contract (api.py), source policy, gates, sandboxed worker,
                   development tool + MCP server, generation harness, arms 1/2a/2b/2c (adapters,
                   selection), frozen set (generated/, strategies.lock.toml)
  campaign/        planned, resumable campaigns: paired seeds, digests, collect, configuration register
  analysis/        equal-weight portfolios, paired stationary bootstrap, Holm
  libraries.py     named primitive sets (WP1 libraries, technical, s2a/s2b/s2c)
  freeze.py        committed freeze manifests (required before any test-year read)
  runner.py        sandboxes -> STGP run -> JSON run record (parallel runs in spawned workers)
tests/             data, leakage, operators (reference implementations), gates, backtest, gp
```

## Setup

```sh
brew install uv                                  # or see https://docs.astral.sh/uv/
uv sync --all-extras                             # uv-managed Python 3.12 + all dependencies (uv.lock)
cp config/paths.example.toml config/paths.toml   # defaults: data/, results/, reports/, cache/ here
git config core.hooksPath .githooks              # enable the hygiene pre-commit hook
```

## Typical commands

```sh
uv run python scripts/download_tier_a.py         # raw pilot data + manifest (free sources, pilot only)
uv run python scripts/build_data.py              # raw -> processed Parquet (offline, causal)
uv run python scripts/data_reports.py            # coverage/gap reports per tier -> reports/wp1
uv run pytest                                    # all tests, incl. real-data gates when data are present
uv run pytest -m "not realdata"                  # what CI runs (synthetic data only, no network)
uv run python scripts/smoke_test.py              # STGP on 2 assets x P01, small budget
uv run python scripts/calibrate.py               # timings for the projections (training data only)
uv run python scripts/project_compute.py         # compute and disk projections -> reports/wp1
uv run python scripts/backup.py                  # one-way backup mirror to backup_dir (Box); --dry-run first
uv run python scripts/generate_strategies.py --preflight   # WP2: isolation test of a generation session
uv run python scripts/generate_strategies.py --dry-run     # WP2: render the briefs and the session command
uv run python scripts/generate_operator_docs.py  # regenerate docs/operators.md after adding an operator
uv run python scripts/update_lock.py             # lock new operator versions (locked ones are immutable)
```

## Data and leakage rules

- Raw data, results, caches and secrets are never committed (`.gitignore`, `scripts/check_hygiene.py` in the pre-commit hook and CI).
- Data paths come from `config/paths.toml` (or `$LPSTGP_PATHS`); nothing is hard-coded. Relative paths are relative to this folder. Working data, results, reports and caches must not be in a cloud-synced folder; only the backup mirror is.
- Modelling code (operators, GP, backtest) cannot import the data layer or do I/O (static policy test). It only ever receives a `Sandbox`, whose arrays end before the stage horizon; the test stage is sealed. Canary tests poison all later rows and check that nothing changes.
- Every operator is prefix-invariant and has an exact, declared lookback (tested bit for bit), and every rule's lookback is capped at 504 bars.
- Every design choice is recorded in `docs/decisions.md`.

## Adding an operator

Add `src/lpstgp/operators/<domain>/<name>__v<n>.py` defining `SPEC = OperatorSpec(...)` with its definition, references and implementation; add a reference test; run the gate suite (`uv run pytest tests/gates tests/operators`), then `scripts/update_lock.py` and `scripts/generate_operator_docs.py`. A change to a locked operator must be a new version file.

## Licence

Not yet chosen (see `docs/decisions.md`, D-007). The repository is private until the licence is set.
