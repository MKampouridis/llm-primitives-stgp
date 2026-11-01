# Prompt for independent code reviews by other LLMs

Used before the WP2 calibration (November 2026) to get code reviews independent of Claude. Give the reviewer the repository at a fixed commit, either as a link to `https://github.com/MKampouridis/llm-primitives-stgp/tree/<commit>` or as an archive:

```bash
git archive --format=zip -o ~/Desktop/lpstgp-$(git rev-parse --short HEAD).zip HEAD
```

The archive holds tracked files only, never data or results. Paste everything below the line.

---

You are reviewing the code of a research project before its large experiments start. Find real defects: places where the code does something different from what it should, in a way that would change scientific results. Results will be frozen, and the held-out test years will be read exactly once, so a defect found afterwards cannot be fixed by re-running. I want findings that are correct, not many findings.

**The project.** Python 3.12. A strongly typed genetic programming (STGP) system evolves per-asset trading rules: an entry tree and an exit tree, each built from typed primitives. Here "operators" means GP primitives (function-set functions), never genetic operators.

The study compares "arms" that differ only in their primitive library, at a matched evaluation budget, with seeds paired across arms. Some arms use whole trading strategies written by an LLM:
- arm 1 selects among them;
- arms 2a, 2b and 2c wrap them, or their parts, as primitives.

Those LLM-written strategies are frozen verbatim in `src/lpstgp/strategies/generated/`. Do not review their content, only how the rest of the code calls them.

**Read first:**
- `docs/protocol.md`: the experimental protocol. It is the specification. Wherever the code and the protocol disagree, that is a finding.
- `CLAUDE.md`: the project's rules, including the data-leakage rules.
- `docs/decisions.md`: the decision log. The entries from D-034 onwards cover this stage. A deliberate, recorded departure from the protocol is not a defect.

**Review these areas, most important first:**
1. **Look-ahead and test-data leakage.**
   - Files: `src/lpstgp/sandbox.py`, `splits.py`, `data/`, `freeze.py`, `pilot.py`, and `scripts/wp2_pilot.py` (steps `freeze` and `pilot-test`).
   - Can any modelling path see a bar after its stage's window, or on or after the data cap of 2008-07-01? Check warm-up and lookback handling, calendar alignment across instruments, forward-filling, rolling statistics and normalisation.
   - Does the test read use exactly what was frozen, and only once?
2. **The backtest and fitness.**
   - Files: `src/lpstgp/backtest/` and `src/lpstgp/gp/fitness.py`.
   - Check signal-to-position timing: a signal computed at close t must not earn bar t's return, and execution lag 2 is the primary setting.
   - Check costs, net returns, minimum activity and segment Sharpe against protocol §5.
3. **The GP engine and the libraries.**
   - Files: `src/lpstgp/gp/`, `runner.py`, `libraries.py`, `strategies/adapters.py`, and `operators/` (a sample of operators for numerical edge cases).
   - Check type safety of crossover and mutation, evaluation counting and the matched budget, the fitness cache and subtree memoisation keys (instrument, stage and parameters), selection by validation, and reproducibility across processes.
   - Is anything able to break the pairing of seeds across arms?
4. **Calibration, the campaign machinery and the go/no-go statistics.**
   - Files: `src/lpstgp/calibration.py`, `campaign/`, `analysis/` and `pilot.py`.
   - Check the protocol's §6 and §8 rules exactly: thresholds, rounding and tie-breaks.
   - Check the bootstrap and the portfolio construction.
   - Can a partial or stale run record be counted as complete?
5. **Tests.** Do the leakage tests in `tests/` test what they claim? They should include prefix invariance, poisoned-future canaries and sealed-stage checks.

**How to work:**
- Trace each suspected defect through the actual code path before reporting it.
- If you can run code, build a minimal reproduction with synthetic data. You have no market data, and you do not need any.
- Say which findings you confirmed by tracing or reproduction, and which are plausible but unconfirmed.
- Do not report style, naming, missing type hints or general refactoring wishes unless they cause a wrong result.

**Report:**
- At most 15 findings, most severe first. For each:
  - file and line;
  - a one-sentence statement of the defect;
  - a concrete failure scenario: which inputs or state lead to which wrong output;
  - severity (critical: invalidates results or leaks test data; major: biases a comparison or a decision rule; minor: latent or small);
  - confidence (confirmed or plausible);
  - a fix in one or two sentences.
- Then a short list of the areas you checked and found sound, so I know what was covered.
- Finally, the commit or archive name you reviewed.
