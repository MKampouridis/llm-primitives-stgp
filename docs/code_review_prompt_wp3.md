# Prompt for independent code reviews of the WP3 machinery by other LLMs

This is M5 of `docs/protocol_wp3.md`, run before WP4 starts. It follows the same procedure as the reviews before WP2's calibration (`docs/code_review_prompt.md`, D-049, D-051).

**What to give the reviewer.** The repository at a fixed commit, as either:
- a link to `https://github.com/MKampouridis/llm-primitives-stgp/tree/<commit>`; or
- an archive (tracked files only, never data or results):

  ```bash
  git archive --format=zip -o ~/Desktop/lpstgp-$(git rev-parse --short HEAD).zip HEAD
  ```

The WP3 changes are the diff `10724f6..<commit>`. Give the reviewer this too, if it accepts a diff:

```bash
git diff 10724f6..HEAD -- src scripts tests > ~/Desktop/lpstgp-wp3.diff
```

Paste everything below the line.

---

You are reviewing the code of a research project before its main experiment (WP4) starts. Find real defects: places where the code does something different from what it should, in a way that would change scientific results. Results will be frozen, and the held-out test years will be read exactly once, so a defect found afterwards cannot be fixed by re-running. I want findings that are correct, not many findings.

**The project.** Python 3.12. A strongly typed genetic programming (STGP) system evolves per-asset trading rules: an entry tree and an exit tree, each built from typed primitives. Here "operators" means GP primitives (function-set functions), never genetic operators. Arms of the study differ only in their primitive library, at a matched evaluation budget, with seeds paired across arms.

This review covers the WP3 code, where an LLM (headless Claude Code sessions) authors and maintains a library:
- **Arm 3:** the LLM authors 28 operators once, and they are then frozen.
- **Arms 4-grow and 4-full:** between GP cycles, the LLM maintains the library (grow; or grow, refine and prune), and every change passes three gates.
- **Arm 5:** the library stays fixed, and the LLM proposes up to 25 entry/exit rule pairs that seed the next cycle's initial populations.

The LLM-written operator files in `src/lpstgp/authoring/generated/` are frozen verbatim. Do not review their content, only how the rest of the code loads, checks and runs them.

**Read first:**
- `docs/protocol_wp3.md` (version 1.0): the specification for this stage. Wherever the code and the protocol disagree, that is a finding.
- `CLAUDE.md`: the project's rules, including the data-leakage rules.
- `docs/decisions.md`, entries D-062 to D-073. A deliberate, recorded departure from the protocol is not a defect.
- `reports/wp3/m4_dryrun.md`: what the dry run showed.

**Review these areas, most important first:**
1. **Leakage into the LLM's inputs and into the evidence.**
   - Files: `src/lpstgp/maintenance/evidence.py`, `knockout.py`, `session.py`, `cycle.py`, `prompts/`, and `src/lpstgp/authoring/mcp_tools.py` (`describe`).
   - Can any brief, evidence figure or tool result reveal test-period data, validation figures, instrument names, dates or prices?
   - Do the knock-outs read only FIT data? Can a knocked-out value enter the run's fitness cache?
   - Is the only feedback from the validation year a single admitted/rejected bit per cycle?
2. **The gates.**
   - Files: `src/lpstgp/maintenance/patch.py`, `gate.py`, `rules.py`, and `src/lpstgp/authoring/gates.py`.
   - Can a patch exceed the per-cycle bounds or the cap, prune an operator the rule does not allow, or change a file outside the patch?
   - Is gate 3 really paired seed for seed, by (instrument, period, seed)?
   - Is the Wilcoxon test one-sided in the right direction (candidate minus current; reject only when the candidate is worse)?
   - Can arm 5's rule text reach `eval` (deap's `PrimitiveTree.from_string`) with an unlisted token?
3. **Library states and provenance.**
   - Files: `src/lpstgp/maintenance/state.py`, `src/lpstgp/authoring/registry.py`, `loader.py`, `libraries.py`.
   - Are states content-addressed and verified on load?
   - Can a refine silently reuse an old identity or GP node name?
   - Can a changed or extra file be loaded without failing?
4. **The cycle and the pairing of arms.**
   - Files: `src/lpstgp/maintenance/cycle.py` and `src/lpstgp/runner.py` (`RunTask` with `knockouts` and `seed_rules`, `parse_tree`), and `src/lpstgp/gp/run.py` (`_initial`, `seeded`).
   - Do seeds depend only on (instrument, period, run), never on arm or cycle?
   - Is a shared batch keyed by everything that changes its results (period, library state and seed rules)?
   - On resume, can a stale or partial run record or session be counted as complete?
   - Does a rejected cycle leave the library and seeds exactly unchanged?
5. **Sandboxing and isolation of the LLM's code.**
   - Files: `src/lpstgp/authoring/worker.py` and `gates.py`, and the session commands in `src/lpstgp/maintenance/session.py` and `src/lpstgp/authoring/generation.py`.
   - Is LLM-written operator code ever imported or executed outside the sandboxed worker before admission?
   - Are the session's tools restricted as the protocol says?
6. **Tests.**
   - Files: `tests/maintenance/` and `tests/authoring/`.
   - Do the leakage tests (poisoned future for the knock-outs, canary scan of the briefs, sealed-stage checks, seed pairing) test what they claim?

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
