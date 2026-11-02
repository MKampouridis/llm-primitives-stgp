# WP2 summary — whole LLM strategies, STGP arms 1–2 and the pilot go/no-go

2 November 2026, about six weeks ahead of the plan's window (14 Dec 2026 – 12 Feb 2027). The protocol is `docs/protocol.md` v1.0; every choice is recorded in `docs/decisions.md` (D-034 to D-061). The primary periods P01–P18 were not touched. The only test data read were the two pilot test years (2006-07 – 2008-06), once, after a committed freeze and the PI's go-ahead (D-058).

**Result: GO.** Primitive-level STGP (arm 2c) is competitive with selecting among the whole LLM strategies (arm 1): the pooled test Sharpe difference 2c − 1 is +0.313, against a non-inferiority margin of −0.2. Under the protocol, the project goes on to WP3/WP4 unchanged.

## What was done

| Step | Outcome | Where |
|---|---|---|
| Strategy generation (M1) | 28 whole strategies, 4 per domain, by isolated headless Claude Code sessions (`claude-opus-5-5`, effort high) on the PI's subscription; 28 of 28 accepted, none repaired, 5 resumed after usage limits. 352 session-minutes; $95 at API prices, no API credit used. Frozen verbatim in `src/lpstgp/strategies/generated/`. | `strategy_generation.md`, D-035, D-044 |
| Code reviews | One internal and two rounds of external review (ChatGPT, Gemini, Antigravity) before any calibration run; the fixes, and a full end-to-end rehearsal of the pilot on synthetic data. | D-047, D-049–D-052 |
| GP calibration (§6.1) | 6 candidates × 120 runs on PL1 training data. Chosen: population 250, tournament 5, 70 generations (17,750 requested evaluations). | `calibration.md`, D-054 |
| Reproducibility on CERES | The CERES node types round differently via numpy's AVX-512 paths; switched off on every node, and enforced. All runs from the budget check on are node-independent. | D-054 |
| Budget unit and λ (§6.2–6.3) | 90 runs, all five GP arms. Budget in requested evaluations (unique-share spread 1.26×, limit 2×); λ_turnover unchanged (no rule without trades; median turnover 11.9 a year). | `budget_check.md`, D-056 |
| Go/no-go campaign | 2 × 1,122 tasks on CERES (22 instruments × 5 GP arms × 10 runs, plus arm-1 selection), about 26 core-hours. Frozen before any test read: 2,244 rule hashes. | `freeze_manifest.json`, D-057 |
| Pilot test read (§8) | Rehearsed on the validation years, then read once. | `pilot_go_no_go.md`, D-058, D-059 |
| Validation–test gap | Same frozen rules on the validation years (VALIDATE data only). | `pilot_validation_gap.md`, D-060 |

## Pilot results (equal-weight portfolios of 22 instruments, net of costs, lag 2)

| Arm | Pooled test Sharpe | PL1 test (2006-07) | PL2 test (2007-08) | vs arm 1 (95% CI) |
|---|---:|---:|---:|---|
| 1 — best whole strategy | 0.374 | 1.695 | −0.602 | — |
| 2a — strategies' entry/exit as terminals | 0.694 | 2.332 | −0.246 | +0.32 [−0.38, +1.01] |
| 2b — strategies' signals at their parameters | 0.747 | 2.238 | −0.006 | +0.37 [−0.33, +1.04] |
| 2c — strategies' signals as typed operators | 0.687 | 2.165 | 0.003 | +0.31 [−0.43, +1.07] |
| 6 — WP1 seed library | 0.634 | 1.918 | −0.022 | +0.26 [−0.47, +0.99] |
| GP-TA — technical analysis | 0.450 | 1.874 | −0.187 | +0.08 [−0.65, +0.80] |
| Buy and hold | 0.934 | 2.128 | 0.142 | +0.56 [−0.08, +1.18] |

In plain terms:

- **Breaking the LLM strategies into primitives and letting the GP recombine them did at least as well as picking the best whole strategy**, and on the point estimate every primitive arm (2a, 2b, 2c) did better, by about 0.3–0.4 Sharpe. None of these differences is statistically clear with two test years; the pilot was designed as a gate, not a test.
- **The finer granularities (2a, 2b, 2c) perform alike.** The pilot cannot tell them apart; that is RQ1, for WP4.
- **Nothing beat buy-and-hold.** Two long-only test years in rising and then falling markets favour holding; every arm is long-only and spends part of the time out of the market. WP4 should report B&H as a benchmark in every comparison, as planned.
- **One regime dominates.** In 2006-07 every arm earned a Sharpe of 1.7–2.3; in 2007-08 (the start of the financial crisis) every active arm was near zero or negative. Pooled figures are mostly the first year.
- **Arm 1 overfits its validation year most.** Selecting the best of 28 strategies on the validation year gives a validation Sharpe of about 4.8 that falls to 1.7 and −0.6 on test. The GP arms fall less (validation about 3–4), and buy-and-hold, which involves no selection, barely moves in PL1. Validation scores are selection-biased for every arm, so these gaps are descriptive.

| Arm | PL1 val → test | PL2 val → test |
|---|---|---|
| 1 | 4.78 → 1.70 | 4.89 → −0.60 |
| 2a | 2.91 → 2.33 | 3.93 → −0.25 |
| 2b | 3.08 → 2.24 | 3.08 → −0.01 |
| 2c | 2.99 → 2.17 | 3.12 → 0.00 |
| 6 | 3.70 → 1.92 | 3.55 → −0.02 |
| GP-TA | 2.82 → 1.87 | 3.26 → −0.19 |
| Buy and hold | 1.95 → 2.13 | 2.13 → 0.14 |

## Deviation from the protocol

§8 also asks for **per-instrument results**. The pilot-test step saved only the portfolio returns per arm, so the per-instrument test figures do not exist, and computing them needs the test years again. They were not recomputed: a second read of the test years would weaken the one-read guarantee, for figures nothing depends on (D-060). Everything else in §8 is reported.

## Reproducibility and hygiene

- Every run record carries its settings, data, library and code digests, its seed and the sandbox access log. The seeds depend only on (instrument, period, run), so all arms are paired.
- 1,259 tests pass (synthetic-data suite, as CI runs it). CI is green.
- The trial register (`reports/configuration_register.csv`) lists every configuration ever planned, for the Deflated Sharpe Ratio in WP4.
- Results stay on the Mac and in the Box mirror, never in git. The test-read claim (`pilot_test_claim.json`) is committed, so the pilot test years cannot be read again by mistake.

## Open items carried into WP3/WP4

1. **WP4 test evaluation:** keep per-instrument series from the start (D-060).
2. **Before WP4:** a review of the data layer and operators by a non-Claude model (planned).
3. **WP3:** the LLM maintenance arms (3–5): which model(s), and the operator-authoring protocol. All LLM work so far ran on the subscription. The open D-031 items on Tier B data, vendor futures and Tier C remain.
4. **Start of WP4:** the runs-per-configuration study (§6.4: 100 runs of arm 2c on PL1/PL2 training data).
5. **Compute:** arm 2c costs about 7× arm 2a per evaluation (4.6 ms vs 0.65 ms). A go/no-go-sized campaign takes about 13 core-hours a period on CERES, so P01–P18 (about 30 instruments, 30 runs) is roughly 1,000 core-hours for these arms, before arms 3–5: a few days on CERES at 60 tasks at a time.
