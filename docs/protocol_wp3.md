# WP3 protocol: LLM-authored and LLM-maintained operator libraries (arms 3, 4-grow, 4-full, 5)

**Status: version 1.0 (3 Nov 2026), fixed before WP4 (D-073).** Draft 0.1 was dated 2 Nov 2026. Written by the engineer under the PI's delegation of scientific decisions (D-042, D-061), after the WP2 pilot (GO, D-059) and before any WP3 code, LLM session or GP run. Choices are recorded in `docs/decisions.md` (D-062 onwards). The values draft 0.1 marked *provisional* were checked by the WP3 dry run (§8, M4) and are fixed in this version, from the mechanics only (D-072, D-073), before any data that the paper reports on are touched. Everything not stated here is as in the WP2 protocol (`docs/protocol.md`): data tiers, costs, execution lag 2, fitness F, final-rule selection on validation, paired seeds, budget in requested evaluations, and the calibrated GP parameters (population 250, tournament 5, 70 generations).

## 1. Purpose

WP3 builds the four LLM library arms and their machinery, and checks the mechanics on pilot training data. It answers no research question itself: RQ2–RQ4 are tested in WP4 on P01–P18.

| Arm | Library | LLM role | Answers |
|---|---|---|---|
| 3 | 28 cross-domain operators authored by the LLM from the domain list, then frozen | author, once | RQ2 (vs arm 6, GP-TA) |
| 4-grow | Arm 3's library, maintained between GP cycles: grow only | maintainer | RQ3 |
| 4-full | Arm 3's library, maintained between GP cycles: grow, prune, refine | maintainer | RQ3, RQ4 |
| 5 | Arm 3's library, fixed; the LLM proposes trees (seeding, semantic mutation, simplification) between GP cycles | tree operator | RQ4 |

Arm 7 (re-implemented ALPHAS2 / EvoQuantLab-style comparators) is out of scope for WP3. It is decided at the start of WP4, if time allows.

## 2. Design principles

1. **One starting point.** Arms 4-grow, 4-full and 5 all start from arm 3's frozen library, so RQ3 and RQ4 compare maintenance regimes and LLM roles, not libraries. For arm 5 this replaces the plan's "fixed 2c grammar". In the plan, 2c used the LLM-written seed library, which is arm 3's library here; WP2 redefined 2c over the strategies' signals (D-037) (D-063).
2. **Identical loop for the LLM arms.** Arms 4-grow, 4-full and 5 run the same cycle: GP runs on training data → evidence → one LLM session → gates → next cycle. They differ only in what the LLM may change: the library (4-grow, 4-full) or the trees seeded into the next cycle (5). The number of sessions, effort and per-session limits are the same, which gives H4's matched LLM budget. Tokens are recorded and reported.
3. **Same reported runs for every arm.** After maintenance, each arm's final library for a period is run like every other arm: 30 or 50 runs per instrument (§6.4 of the WP2 protocol), same budget and seeds. Maintenance cycles cost extra GP evaluations and LLM tokens. These are reported as the price of the method, not hidden in the comparison (D-066).
4. **The LLM never sees prices, dates, instrument names, test data, our code, the WP1 operators (arm 6) or the WP2 strategies.**

## 3. Arm 3: authoring the library

- **Mechanism:** isolated headless Claude Code sessions, as in WP2 (D-035):
  - model `claude-opus-5-5`, effort high, on the PI's subscription;
  - `--restricted` file tools in a neutral folder, no shell, no web, no CLAUDE.md, memory or skills;
  - our own MCP tools only.
- **Free authoring, not re-implementation (D-062).** The brief gives the domain name and a one-line scope, plus the operator contract and the semantic types. The scope is the WP2 strategy brief's wording without its "(for example …)" lists, which name many of arm 6's operators. The plan's example operators are not given either. A test checks every brief for arm 6's operator names and the plan's examples (D-069). So the LLM chooses which mathematics to implement, and H2a compares an LLM-chosen and LLM-written library with an expert-specified one (arm 6: expert-specified, AI-assisted, expert-verified; D-002).
- **Quota:** 4 operators per domain × 7 domains = 28, as in arm 6.
  - One session per domain, run in order.
  - Each later session sees the names and signatures of the operators already accepted in other domains, so that it can avoid duplicates.
- **Shared parts:** the data terminals (3) and the core glue (17: constructors, adaptive thresholds, comparators, logic, regimes) are the WP1 ones, shared with arm 6. Only the cross-domain operators differ between arms 3 and 6.
- **Contract (D-069).** The session sees a self-contained `operator_api.py`, with no project code; the host binds it to the real types.
  - Operators output a scale-free `Real`, like all 28 of arm 6's cross-domain operators. Thresholds, comparisons and logic stay in the shared core.
  - An operator with a Series or Path input must be scale-invariant, and one with a Path input shift-invariant. These are tested.
  - Parameters use the five standard kinds (Window, LongWindow, Lag, Quantile, KSigma) or kinds the LLM declares itself (2–9 values). Arm 6's own kinds (for example for embedding orders or p-variation exponents) are not shown, because they would point to its operators.
  - Arm 3's operators have no independent reference tests; they are admitted by the gates alone. This is part of their lower human effort (H2a).
- **Tools:**
  - `check`: the WP1 admission gates. Compile and the source policy (the stricter WP2 one), types, parameter grids, finite and non-constant output, determinism, exact lookback, prefix invariance, declared invariances, runtime, and finite non-constant output on dev-fit data. Cross-process determinism is checked at acceptance.
  - `describe`: descriptive statistics of an operator's output on anonymised dev-fit data. These are the finite share, quantiles, lag-1 autocorrelation and the correlation with the session's other operators.
  - There is no backtest tool. Arm 6 was written without performance feedback, so arm 3 is too (D-062).
- **Budget:** up to 100 `check` and 50 `describe` calls per session.
- **Acceptance:** exactly four operator files, all passing, with names and declared kinds that do not clash with earlier domains. As for WP2 strategies, a failure gets one repair turn, then one fresh re-run of the session. The accepted files are frozen verbatim in `src/lpstgp/authoring/generated/arm3/`, under `src/lpstgp/authoring/arm3.lock.toml`, outside the WP1 registry (D-070), and documented in `docs/operators_arm3.md`.
- **Effort record (H2a):** session minutes, tokens and human minutes. The human minutes should be zero apart from launching, which is the point of H2a.

## 4. The maintenance cycle (arms 4-grow, 4-full, 5)

Per walk-forward period (WP3: PL1 then PL2; WP4: P01–P18), run C cycles on the period's training data. Then hand the library on to the next period:

```
L(p, 0) = L(p-1, C)        (L(0, 0) = arm 3's library)
for c in 1..C:
    GP runs with L(p, c-1) on FIT data            -> run records
    evidence from those records (FIT only)        -> evidence table
    one LLM session                               -> proposed patch
    gates (incl. paired-seed check on VALIDATE)   -> admitted patch
    L(p, c) = L(p, c-1) + admitted patch
reported runs for period p use L(p, C)
```

- **Causality.** Maintenance for period p sees only period p's FIT and VALIDATE years, which end before p's test year. Carrying the library forward is causal, because L(p-1, C) used only data before p's test year (D-064).
- **Cycles:** C = 3 per period. That gives 6 cycles in the WP3 dry run and 54 over P01–P18.
- **Cycle runs:** 3 runs per eligible instrument, at the calibrated GP parameters, on FIT data. The seeds come from (instrument, period, run), never from the arm or the cycle, so the three LLM arms share them, and every cycle of a period uses the same seeds. The runs of a patched library are then both the gate's paired-seed check (§4.3) and, if the patch is admitted, the next cycle's runs. No extra GP runs are needed.
- **Where it runs:** wholly on the active Mac (D-065). An arm-3-sized cycle takes about 15–20 minutes on 6 workers, judging by arm 6's cost in the budget check (about 90 runs at about 63 s each), plus the knock-outs. So a period takes about an hour per arm, and WP4's maintenance needs about 60–80 Mac-hours over the three arms. Running on the Mac avoids a CERES round trip with two-factor sign-in at every cycle. The reported runs go to CERES, as in WP2. If M4 shows the Mac is too slow, the cycles move to CERES, with the LLM session still on the Mac.

### 4.1 Evidence, per operator (training data only)

| Measure | Definition |
|---|---|
| usage | Share of the final hall-of-fame rules (all instruments and runs) whose entry or exit tree contains the operator |
| survival | Mean share of generations in which the operator appears in the best individual of a run |
| knock-out contribution | Mean drop in FIT fitness F of the hall-of-fame rules that use the operator when every node of it is replaced by its neutral value: for a Real output, its median on the run's FIT data; for a Bool output, "unknown" (Kleene NaN) |
| stability | Spread (interquartile range) of the knock-out contribution across instruments and across the half-year FIT segments |
| cost | Median milliseconds per call |
| lineage | Version, cycle of entry, and the previous evidence rows |

The maintainer also receives the library's contracts and its own code (arm 3's lineage only), the domain list, and the elite trees in readable form. Instruments are anonymised as in WP2, with asset class only.

### 4.2 What the LLM may do per cycle

| Arm | Prune | Refine (new version replaces old) | Grow | Library cap |
|---|---:|---:|---:|---|
| 4-grow | — | — | ≤ 2 | 64 cross-domain operators |
| 4-full | ≤ 2 | ≤ 2 | ≤ 2 | 64 cross-domain operators |
| 5 | — | — | — | fixed (arm 3) |

- **Prune** needs low usage and low contribution in at least 2 consecutive cycles, checked by the gate rather than left to the LLM. *Low* means the library's bottom quarter by both measures, and the brief marks the operators that qualify (D-072; the fixed thresholds of D-071 were never met in M4). A pruned operator can come back only as a new grow.
- **Refine** issues a new version under a new identity (contracts are immutable). Its lineage is kept, and the old version retires.
- **Core glue and data terminals** are never pruned or refined. Every grown operator is in one of the 7 domains, so the domain quota is not fixed after arm 3.
- **When 4-grow reaches the cap** it stops growing. Each period's report records whether the cap was hit (D-067). These limits are fixed at 1.0 (D-073). The dry run suggests the cap may be reached around WP4 period 6–8.

**Arm 5's session** proposes up to 25 entry/exit rule pairs over arm 3's library. They may be new seeds, semantic mutations of elite trees, or simplifications. Each pair is parsed against the typed primitive set; a pair that fails parsing or the type check is discarded. The admitted pairs replace 25 of the 250 random individuals in the initial population of every run in the next cycle and in the period's reported runs. Arm 5 never changes the library.

### 4.3 Gates for a patch

1. Every new or refined operator passes the WP1 admission gates (as `check`). Its code meets the source policy and runs under `sandbox-exec` on the Mac before it is ever imported.
2. The bounds and the cap of §4.2 hold, and prunes meet the evidence rule.
3. **Paired-seed check:** the patched library's runs (the next cycle's runs) are paired with the previous library's runs at the same seeds, and their final rules are scored on VALIDATE. The patch is rejected only when a one-sided Wilcoxon signed-rank test on the paired differences in validation F finds it worse at α = 0.05 (D-072 replaced the first rule, median difference below −0.05, which M4 showed rejected about a third of harmless patches). This is a guard against harm, not a search for improvement. Because it uses the validation year, it can only *widen* the validation–test gap of the maintained arms, so it works against H3 and is conservative (D-066).
4. If a patch is rejected, the library stays the same for the next cycle. The rejection and its reason are part of the evidence the LLM sees next.

Arm 5's trees pass gates 1–2 as type checks (they add no code) and gate 3 like a patch (D-071).

## 5. Storage and provenance

- Each library state is a content-addressed set of operator files with a lock: (name, version, code hash, semantic fingerprint).
- Arm 3's library is committed to git (frozen LLM output, never edited).
- The maintained states live under `results/wp3/` (git-ignored, mirrored to Box). A **lineage manifest** is committed per period and arm, holding the hashes of every state, patch, gate result and session transcript. The final libraries are released with the paper's artefact (C6).
- Each LLM session is archived as in WP2: stream-json transcript, brief and its hash, model ids, tokens and estimated cost, and tool calls.

## 6. Budget and pacing

- **Arm 3:** 7 sessions.
- **WP3 dry run:** 2 periods × 3 cycles × 3 arms = 18 sessions.
- **WP4:** 18 periods × 3 cycles × 3 arms = 162 sessions.
- In the M4 dry run, a maintenance session took 3.4 minutes on average, about $0.65 at API prices. At that rate WP4 needs about 9 hours of session time, about $105 at API prices, and about 34 Mac-hours for the cycles' GP runs. This replaces draft 0.1's estimate from WP2 (about 32 hours, about $550). The sessions run on the subscription, paced one session at a time (D-044). It does not fit the $60 a month API budget, so subscription use is assumed throughout. Usage beyond the subscription's monthly limit stops rather than being billed (D-068), so the constraint is time: M4 showed that WP4's sessions fit, so C stays at 3.

## 7. Leakage tests (with the code, before any session)

- Prefix invariance and poisoned-future canaries for every evidence measure: changing data after the period's VALIDATE end changes nothing.
- The maintainer's inputs are checked to contain no dates, prices or instrument names: an automated scan of the rendered brief and evidence, with canary strings.
- Sealed-stage checks: the cycle and gate code can open FIT and VALIDATE only.
- Paired seeds across arms are checked in every cycle plan.

## 8. WP3 milestones

| | Milestone | Needs |
|---|---|---|
| M1 | Arm 3 machinery: operator brief, `check`/`describe` MCP tools, session driver (reusing WP2's), pre-flight isolation session | code; one short pre-flight session |
| M2 | Arm 3 authoring: 7 sessions, freeze and lock, `docs/operators_arm3.md` | **PI go-ahead** (subscription use) |
| M3 | Maintenance machinery: cycle planner, evidence (§4.1), maintainer and arm-5 briefs and tools, patch format, gates (§4.3), lineage storage, leakage tests | code |
| M4 | Dry run on PL1 → PL2 training data, all three LLM arms. Checks the mechanics only: patch admission rates, library sizes, cap hits, tokens, time, failure modes. Validation only; no test data (the pilot test years are spent) | **PI go-ahead** (18 sessions) |
| M5 | Protocol 1.0: the provisional values fixed from M4's mechanics, never from performance; code review by a non-Claude model, as planned before WP4 | PI (review by other LLMs) |

The dry run checks whether the machinery works. It is not used to choose between arms or to tune them on performance. Any provisional value changed after M4 is changed for a mechanical reason, such as patches that never pass the gates or caps reached in the first period, and is logged here.

## 9. Change log

- **2 Nov 2026, draft 0.1:** written (engineer, under D-042/D-061). Decisions D-062–D-067.
- **2 Nov 2026, M1 (arm 3 machinery):** the arm-3 contract and brief made concrete (D-069). Usage beyond the subscription's limit stops rather than being billed (D-068).
- **2 Nov 2026, arm-3 isolation pre-flight:** archived in `results/wp3/preflight/20261102T232857Z/`.
  - The session's tools were exactly Read, Write, Edit, Glob, Grep, `check` and `describe`.
  - Reads of the repository, the home folder and the parent folder were refused.
  - There was no shell or web tool, and no CLAUDE.md, memory or skills were loaded.
  - `check` and `describe` worked on a toy operator (21 dev-fit instruments).
  - The model was `claude-opus-5-5` throughout.
  - As in WP2, Claude Code attached the account e-mail address to the context.
- **3 Nov 2026, M2 (arm 3 authored and frozen, D-070):** 8 sessions, 51 minutes of session time, `claude-opus-5-5` throughout, no tools beyond the seven allowed.
  - Information theory's first session left a superseded draft in its folder, which it could not delete (no shell). The final check counted five files, so the session failed after its repair turn. Its fresh re-run was accepted, and the first attempt's operators are not used.
  - The other six domains were accepted at the first attempt. One kind was declared (`DccaBox`).
  - 28 operators frozen (lock `6d97234bda3f`). Report: `reports/wp3/arm3_authoring.md`; catalogue: `docs/operators_arm3.md`.
  - One name coincides with arm 6: `permutation_entropy`.
- **3 Nov 2026, M3 (maintenance machinery, D-071):** `src/lpstgp/maintenance/` and `scripts/maintain.py` (`--stub`, `--preflight`, the cycles).
  - The patch format is file-based (grow, refine, or prune by emptying a file). The prune thresholds are provisional.
  - The LLM is told only admitted or rejected, never a validation figure.
  - Arm 5 also gets gate 3 (this changes §4.3).
  - Batches of runs are shared across arms by content.
  - A token whitelist guards the parsing of arm 5's trees.
  - The maintainer pre-flight passed for both tool sets.
- **3 Nov 2026, M4 (dry run, D-072):** 18 sessions on PL1 → PL2, all completed on `claude-opus-5-5`, with no repair turns. 9 of 18 proposals admitted. Wall clock 3 h 49 min (about 12.7 minutes per cycle), 246k output tokens, no bill. Report: `reports/wp3/m4_dryrun.md`; lineage: `reports/wp3/m4_lineage/`.
  - The prune rule could never be met, so it was made relative (§4.2).
  - Gate 3's threshold sat inside the noise, so it was replaced by a one-sided Wilcoxon test (§4.3).
  - WP4's maintenance is re-estimated at about 34 Mac-hours, against the 60–80 in §4.
  - Re-check of 4-full under D-072 (6 sessions): pruning used in 3 of 6 cycles, every patch admitted, no failures.
- **3 Nov 2026, version 1.0 (M5, D-073):** the provisional values are fixed as they stood after D-072:
  - C = 3 cycles per period;
  - 3 runs per instrument;
  - bounds 2 grows, 2 refines and 2 prunes per cycle;
  - a cap of 64;
  - 25 arm-5 seeds;
  - tool budgets of 100/50/30 for the maintainers and 30 for arm 5;
  - the relative prune rule (bottom quarter, two consecutive cycles);
  - gate 3 as a one-sided Wilcoxon test with α = 0.05.

  §6's estimate is updated from the dry run. Next is the code review by non-Claude models (`docs/code_review_prompt_wp3.md`).
