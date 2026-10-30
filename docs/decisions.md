# Decisions and assumptions

Every assumption and design choice made while building the code base, in the order made. The research plan (`docs/research_plan.md` in the Box project folder) is authoritative; where an entry departs from it or fills a gap, it says so.

Status: **Decided** = agreed with the PI. **Provisional** = engineer's default, open for review. **Open** = needs a decision before the work package named.

---

## WP1 (from 30 Oct 2026)

### D-001 Repository location — Decided
The git repository is a local clone at `~/code/llm-primitives-stgp`, outside Box; the private GitHub repository is the code backup. The Box project folder keeps the plan, survey and notes, and receives generated reports (`reports/wp1/`) and results (`results/`) through paths in `config/paths.toml`.
*Why:* Box Drive syncs files while git rewrites `.git` (index, refs, packs), which can corrupt the repository or leave conflict copies; Box would also sync `.venv` and caches.

### D-002 Arm 6 (expert-written control) provenance — Decided
The WP1 seed library is written by Claude Code (`claude-opus-5-5`) in an interactive session, without API calls, and serves as arm 6. It is described as **expert-specified, AI-assisted, expert-verified**. Each operator contract records its provenance; the PI's review time per operator is logged in `docs/arm6_review.md` and is arm 6's "human effort" for H2a. The arm-3 authoring prompts in WP3 must contain only the domain list and the contract specification, never this code.
*Departure from the plan:* Method §1 says the seed library is LLM-written, and arm 6 is "expert-written versions of arm 3's operators". Both wordings need updating in the plan.

### D-003 Python and tooling — Decided (plan approval)
CPython 3.12 managed by uv; `requires-python >= 3.12`. The brief asks for 3.11+; 3.12 is the minimum because the test-only reference libraries nolds 0.6.3 and PyWavelets 1.10 need it. Only uv-managed interpreters are used (`python-preference = "only-managed"`; currently 3.12.16), so the local build matches CI and never picks up the Anaconda or Homebrew Python. pytest (+ xdist, Hypothesis) and ruff (lint and format). uv installed with Homebrew. All versions are pinned in the committed `uv.lock`.

### D-004 Continuous integration — Decided (plan approval)
GitHub Actions on every push and pull request: Ubuntu, Python 3.12, `uv sync --locked`, ruff lint and format checks, the hygiene check, and `pytest -m "not realdata"`. Tests never call the network. Tests that need the local Tier A data carry the `realdata` marker and are skipped in CI, where synthetic data stand in. One BLAS/numba thread per process.

### D-005 Data and secrets never enter git — Decided
`.gitignore` excludes data, results, reports, caches, `.env*`, keys and credentials, and `config/paths.toml`. `scripts/check_hygiene.py` (run by the `.githooks/pre-commit` hook and in CI) rejects data file types, files over 512 KB (except `uv.lock`) and secret-like strings. Secrets are read from the environment only; WP1 needs none.

### D-006 Commit identity — Provisional
Commits use the machine's global git identity. Change with a repo-local `git config user.email` if an institutional identity is preferred.

### D-007 Licence — Open (before the repository is made public)
No licence file yet; the plan defers the choice to submission or preprint time. DEAP is LGPL-3.0, which allows use as an imported dependency.
