# WP3 M4: maintenance dry run (mechanics only)

3 Nov 2026, code version 9c040d3. Arms 4-grow, 4-full and 5, periods PL1 then PL2, 3 cycles each: 18 LLM sessions (`claude-opus-5-5`, effort high, headless Claude Code on the PI's subscription). Each cycle used 66 GP runs (22 pilot instruments × 3 runs, population 250, 70 generations) on FIT data, and gate 3 used the VALIDATE year. No test data were read. As the protocol requires (§8), this report covers how the machinery behaved. It does not compare arms and is not used to tune them. Lineage manifests: `reports/wp3/m4_lineage/`; full archive: `results/wp3/maintenance/dryrun/` (git-ignored, mirrored to Box).

## In short

- **The machinery worked end to end.**
  - All 18 sessions completed on the right model.
  - Every patch and rule set passed the host's final check (gates 1–2) at the first attempt, so no repair turns were needed.
  - No tool budget came near its limit: at most 4 of the 100 `check` calls were used.
  - Every library state loaded and verified its hashes.
  - All three arms shared the first PL1 batch, as designed.
- **Two provisional rules did not work mechanically.** Both are changed in D-072.
  1. *Prune rule.* It could never be met. Across all 356 operator-cycles, usage was at least 0.021 (threshold 0.02) and contribution at least 0.41 (threshold 0.01). So 4-full never had the option to prune and differed from 4-grow only by refines. **Fix:** a relative rule. An operator may be pruned if it is in the library's bottom quarter by both usage and contribution in two consecutive cycles, and the brief marks which operators qualify. On this run's evidence, that would have allowed one to three candidates in about a third of the cycles.
  2. *Gate 3.* It was dominated by noise. Two replicate batches of the same library, with the same instruments and different seeds, give a median paired difference whose standard deviation is about 0.13 over 66 pairs. A threshold of −0.05 therefore rejects about a third of patches that do no harm. The observed medians ranged from −0.30 to +0.27, and the bootstrap 95% interval of each one spanned about 0.3–0.9. **Fix:** reject only when a one-sided Wilcoxon signed-rank test on the paired differences finds the candidate worse at α = 0.05. Applied after the fact to this run's pairs, 4 of the 18 proposals would have been rejected, against 9 under the old rule.
- **Time:**
  - The run took 3 h 49 min of wall clock, about 12.7 minutes per cycle.
  - Of that, 61 minutes were LLM session time and the rest was GP runs and knock-outs, at about 8 minutes per batch of 66 runs on 6 workers.
  - At this rate, WP4's 162 cycles need about 34 Mac-hours, under the protocol's estimate of 60–80. The cycles stay on the Mac.
- **Tokens:**
  - 246k output tokens in total.
  - About $11.62 at API list prices. Nothing was billed (subscription, D-068), and no usage limit was reached.

## Per cycle

| arm | period | cycle | proposal | decision | median Δ val. F | p (harm) | library size before → after |
|---|---|---|---|---|---:|---:|---|
| 4-grow | PL1 | 1 | 2 grows | admitted | −0.005 | 0.36 | 28 → 30 |
| 4-grow | PL1 | 2 | 2 grows | rejected | −0.276 | 0.013 | 30 → 30 |
| 4-grow | PL1 | 3 | 1 grow | rejected | −0.095 | 0.051 | 30 → 30 |
| 4-grow | PL2 | 1 | 2 grows | rejected | −0.091 | 0.27 | 30 → 30 |
| 4-grow | PL2 | 2 | 2 grows | admitted | +0.052 | 0.59 | 30 → 32 |
| 4-grow | PL2 | 3 | 2 grows | admitted | +0.093 | 0.88 | 32 → 34 |
| 4-full | PL1 | 1 | 2 grows, 1 refine | rejected | −0.297 | 0.031 | 28 → 28 |
| 4-full | PL1 | 2 | 1 grow, 1 refine | admitted | −0.005 | 0.46 | 28 → 29 |
| 4-full | PL1 | 3 | 2 grows | rejected | −0.210 | 0.070 | 29 → 29 |
| 4-full | PL2 | 1 | 1 grow | admitted | +0.176 | 0.66 | 29 → 30 |
| 4-full | PL2 | 2 | 2 grows, 1 refine | admitted | +0.007 | 0.56 | 30 → 32 |
| 4-full | PL2 | 3 | 2 grows, 1 refine | admitted | +0.095 | 0.63 | 32 → 34 |
| 5 | PL1 | 1 | 25 rule pairs | rejected | −0.110 | 0.092 | 28 (fixed) |
| 5 | PL1 | 2 | 25 rule pairs | rejected | −0.139 | 0.044 | 28 |
| 5 | PL1 | 3 | 24 rule pairs | rejected | −0.204 | 0.042 | 28 |
| 5 | PL2 | 1 | 25 rule pairs | admitted | +0.268 | 0.96 | 28 |
| 5 | PL2 | 2 | 25 rule pairs | admitted | +0.000 | 0.39 | 28 |
| 5 | PL2 | 3 | 25 rule pairs | admitted | +0.041 | 0.80 | 28 |

Decisions were made under the rule in force during the run (reject if median Δ < −0.05). The p-values are computed after the fact, for D-072. Δ val. F is the candidate's paired difference from the current library on the VALIDATE year. It was never shown to the LLM.

## Mechanics in detail

- **Admission:** 9 of 18 admitted (4-grow 3/6, 4-full 4/6, arm 5 3/6). The rejections cluster in PL1 (7 of 9 PL1 proposals across all three arms) against 2 of 9 in PL2. Within a period, every cycle and every arm is compared with batches at the same seeds, and for arm 5 with one unchanged baseline batch. So the luck of one baseline batch is shared by all the decisions made against it. The old threshold, set well inside the noise, magnified that. This is a further reason for a test calibrated to the noise (D-072). It is not a finding about the arms.
- **Library sizes and the cap:**
  - Both maintained libraries grew from 28 to 34 operators. No grow was refused by the cap of 64, and no prune happened, because the rule could not be met (above).
  - At this run's rate (about one admitted grow per cycle), 4-grow would reach the cap after about 30 more admitted grows, around WP4 period 10–12. The protocol expects this and records it (D-067).
- **Refines:** 3 were admitted in 4-full (versions 2 of three operators). Refines and grows used separate files and passed the cross-process determinism check.
- **Arm 5:**
  - Proposals were full or nearly full (24–25 pairs). Sessions were short: 6 turns and about 1.5 minutes each.
  - The seeded pairs rarely survive as a run's final rule: 0–2 of 66 runs, though 6–17 runs keep one in the hall of fame. Twenty-five seeds in a population of 250 are quickly diluted by evolution, and the H4 analysis should note this.
  - An admitted set carried over to the next cycle as designed: PL2 cycles 2–3 started from 25 seeds.
- **Sessions:**
  - 2–8 minutes and 13–27 turns for the maintainers.
  - 1–4 `check` and `describe` calls and 1–2 `check_patch` calls each.
  - Arm 5 used one `check_rules` call each.
  - No session failed, timed out, used another model or needed a repair turn.
- **Warnings:** an operator grown in 4-full (`pointwise_holder_exponent`, PL2 cycle 2) raises numpy "invalid value" warnings on windows where it is undefined. It returns missing values there, as the contract allows. The warnings are harmless and only make `driver.log` long.
- **Leakage:** all 1,452 run records' sandbox reads were FIT and VALIDATE only, ending at or before the period's test start (the same check as the real-data test). The briefs contained no validation figures, by construction and by test.

## Changes for protocol 1.0 (mechanical reasons only; D-072)

1. The prune rule becomes relative: bottom quarter by both usage and contribution, in two consecutive cycles, and the brief marks the operators that qualify.
2. Gate 3 becomes a one-sided Wilcoxon signed-rank test (reject when p < 0.05) on the same 66 paired validation differences.

Everything else stays as provisionally set:

- C = 3 cycles per period;
- 3 runs per instrument;
- the per-cycle bounds;
- the cap of 64;
- 25 seeds for arm 5;
- the tool budgets.

None of these showed a mechanical problem.

Neither change has yet run with a real LLM session. A short re-check of 4-full alone (PL1 → PL2, 6 sessions, about 1.3 hours) would exercise the new prune path before WP4. Whether to run it is for the PI to decide.

## Re-check of 4-full under D-072 (3 Nov 2026, PI go-ahead)

Campaign `recheck`: 4-full only, PL1 → PL2, 3 cycles each, the new prune rule and gate, same seeds and settings. Archive: `results/wp3/maintenance/recheck/`; lineage: `reports/wp3/m4_lineage/recheck_4-full_*.json`.

| period | cycle | proposal | prunable (marked in brief) | decision | median Δ val. F | p (harm) | library |
|---|---|---|---|---|---:|---:|---|
| PL1 | 1 | 2 grows, 1 refine | – (first cycle) | admitted | −0.127 | 0.25 | 28 → 30 |
| PL1 | 2 | 2 grows, 1 prune | `dcca_coefficient` | admitted | +0.038 | 0.37 | 30 → 31 |
| PL1 | 3 | 2 grows | none | admitted | −0.058 | 0.68 | 31 → 33 |
| PL2 | 1 | 2 grows, 1 prune | `net_transfer_entropy` | admitted | −0.085 | 0.22 | 33 → 34 |
| PL2 | 2 | 2 grows, 1 prune | `generalized_hurst_spread` | admitted | +0.351 | 1.00 | 34 → 35 |
| PL2 | 3 | 2 grows | none | admitted | −0.240 | 0.066 | 35 → 37 |

- **The prune path works.**
  - The rule marked one operator as prunable in 3 of the 6 cycles, and the LLM pruned it each time.
  - Each prune passed the gate's own check of the rule, and the pruned operators left the library state as retired.
  - The LLM never tried to prune an unmarked operator.
- **The gate admitted all 6 patches.**
  - The old rule would have rejected 4 of them (medians −0.127, −0.058, −0.085, −0.240).
  - The closest call was PL2 cycle 3 (p = 0.066).
  - This is the intended behaviour of a harm guard calibrated to the noise: about 5% false rejections, rather than about a third.
- **The library grows faster.** The net growth was +9 operators in 6 cycles, since grows are rarely refused and prunes are at most one per cycle in practice. At this rate 4-grow and 4-full would reach the cap of 64 around WP4 period 6–8, not 10–12. The cap and its hits are recorded per period as designed (D-067); this is an expected consequence, not a fault.
- **Mechanics:**
  - 6/6 sessions completed on `claude-opus-5-5`, with no repair turns and no problems at the host's check.
  - 25.5 minutes of session time, about $5.38 at API prices (subscription, not billed).
  - The whole run took 1 h 10 min of wall clock.

With both changes now exercised by real sessions, the provisional values go to protocol 1.0 (M5) as they stand.
