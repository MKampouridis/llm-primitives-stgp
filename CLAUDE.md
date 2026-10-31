# Project rules for coding sessions

Research code for a journal paper: can an LLM author and maintain the typed primitive set of a strongly typed GP (STGP) that evolves per-asset entry/exit trading rules? *Operators* means GP function-set functions, never genetic operators. The PI is Michael Kampouridis.

## Sources of truth

- `docs/research_plan.md` is authoritative (exported from the live plan document). If anything conflicts with it, ask the PI.
- `docs/decisions.md` records every assumption and choice: number, status (**Decided** = agreed with the PI, **Provisional** = engineer's default, **Open**), the reason, and any departure from the plan. Add an entry for every new choice.
- Work packages: WP1 (library and harness) is done. Read the latest `reports/<wp>/` summary and the open-questions entry in `docs/decisions.md` before starting work.

## Hard rules

1. **Never look at, load or tune on test-period data.** Modelling code (operators, GP, backtest, strategies, LLM prompts and evidence) gets data only through `Sandbox` in the FIT or VALIDATE stage; the TEST stage is sealed. Data reports give counts only, never prices, returns or performance. Test data are unsealed only by an explicit PI decision, recorded in `docs/decisions.md`.
2. **No secrets in code, config or commits.** Read API keys and credentials from the environment only.
3. **Never commit data, results or caches.** `.gitignore`, the pre-commit hook and CI (`scripts/check_hygiene.py`) enforce this.
4. **Storage:** store per-run summaries and best individuals only, never whole populations per generation. Caches are disposable, size-capped and git-ignored.
5. **Locked operator contracts are immutable** (`src/lpstgp/operators/registry.lock.toml`). A change means a new version file, then `scripts/update_lock.py` and `scripts/generate_operator_docs.py`.
6. **Ask before outward-facing or costly actions:** GitHub settings, paid LLM API calls beyond an agreed budget, deleting data or results, unsealing test periods.
7. Paths come from `config/paths.toml` (relative to this folder); never hard-code them. Working paths stay out of cloud-synced folders; Box is only a backup mirror written by `scripts/backup.py`.

## Working practice

- Every commit: `uv run ruff check . && uv run ruff format --check . && uv run pytest -m "not realdata" -n auto`. Also run `uv run pytest` (real-data gates) after data-layer or operator changes. CI must stay green.
- Commit at each milestone and push; run `scripts/backup.py` at milestones.
- Leakage tests come with every new feature module: prefix invariance, poisoned-future canaries, sealed-stage checks.
- Randomness is seeded and reproducible across processes. Seeds depend only on (instruments, period, run index), never on the arm, so that arms are paired.
- Numba: no `fastmath`, no `parallel`. One BLAS/numba thread per worker process.
- Write in British English. Summarise each milestone in plain language.

## Commands

```sh
uv sync --all-extras                          # environment (uv-managed Python 3.12, uv.lock)
uv run pytest -m "not realdata" -n auto       # what CI runs
uv run pytest -n auto                         # everything, incl. real-data gates
uv run python scripts/backup.py --dry-run     # check the Box mirror before writing it
```
