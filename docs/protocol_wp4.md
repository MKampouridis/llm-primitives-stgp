# WP4 protocol: all arms on the primary periods P01–P18

**Status: draft 0.1 (3 Nov 2026).** Written by the engineer under the PI's delegation of scientific decisions (D-042, D-061), before any WP4 code is written, any WP4 run is made or any data from P01–P18 is read. Choices are recorded in `docs/decisions.md` (D-075 onwards). Items marked *provisional* are fixed at version 1.0, before the first WP4 run. Items marked **PI** need a decision from the PI because they concern data, infrastructure or cost (CLAUDE.md rule 7).

Everything not stated here is as in:
- **the WP2 protocol** (`docs/protocol.md` v1.0): data tier A, costs, execution lag 2, fitness F with the calibrated λ, final-rule selection on validation, paired seeds, the budget in requested evaluations (17,750 per run: population 250, tournament 5, 70 generations), run records, campaign plans and the trial register;
- **the WP3 protocol** (`docs/protocol_wp3.md` v1.0): arms 3, 4-grow, 4-full and 5, the maintenance cycle and its gates.

## 1. Purpose

WP4 answers RQ1–RQ4 on the 18 walk-forward periods of tier A. It is the paper's confirmatory experiment: its test years are read once, after every rule of every arm has been frozen. The post-cutoff window is reported separately (§2). Tiers B and C are separate, later campaigns (§9).

## 2. Data, periods and the data cap

- **Tier A**, daily bars, close-only terminals: the 31 instruments of D-013, eligible per period by D-009. That gives **496 eligible (instrument, period) pairs**: 25 instruments in P01, rising to 31 from P15. An instrument that is not eligible in a period is not run there and has no weight in that period's portfolio.
- **Final data (PI).** Two choices:
  - **Vendor data:** back-adjusted continuous futures for the COMEX metals, a Bund future, and WTI without the EIA gaps (D-031 item 11). This needs a data source from the PI.
  - **The free WP1/WP2 sources as they stand,** with the proxies and roll gaps disclosed (D-013).

  The engineer's default is the free sources, so that WP4 is not held up. Any data change must be made before M2, because changing data afterwards invalidates every plan's data digest.
- **Primary periods P01–P18:** fit 2 years, validation 1 year, test 1 year. P01's fit starts on 2005-07-01, and the anchor steps by one year. P18's test year is 2025-07 to 2026-06. Test years are period-relative (D-017): period p's validation year is period p−1's test year. Using it for period p's modelling is causal, because the rules of period p−1 never depend on it.
- **Post-cutoff window PC (D-036):**
  - fit 2023-07-01 to 2025-06-30, validation 2025-07-01 to 2026-06-30, test from 2026-07-01 to the last bar in the data at the PC freeze;
  - its test year lies wholly after the training cutoff of `claude-opus-5-5` (June 2026), which wrote every LLM artefact;
  - it is run like P01–P18, but frozen and read in a separate, later step (M7), and reported separately;
  - a test window of less than 6 months at the planned date is still reported, with its length stated.
- **Data cap.** The WP2 cap (no modelling read on or after 2008-07-01) is lifted by a PI decision recorded in `docs/decisions.md` at M1, and replaced by stage sealing:
  - modelling code may open the FIT and VALIDATE stages of P01–P18 and PC;
  - the TEST stage of any of these periods opens only through a freeze-checked test reader, once (§6);
  - the pilot periods' test years stay spent.

## 3. Arms

| Arm | Library or rule source | Answers | Status |
|---|---|---|---|
| 1 | The 28 frozen whole LLM strategies; the best one per instrument on validation | RQ1 | confirmatory |
| 2a | STGP over the strategies' entry and exit signals | RQ1 | confirmatory |
| 2b | STGP over the strategies' signal series at their own parameters | RQ1 | secondary |
| 2c | STGP over the strategies' signals as typed operators | RQ1 | confirmatory |
| 3 | Arm 3's frozen LLM-authored library (28 operators) | RQ2 | confirmatory |
| 4-grow | Arm 3's library, maintained (grow only) per period | RQ3 | confirmatory |
| 4-full | Arm 3's library, maintained (grow, prune, refine) per period | RQ3, RQ4 | confirmatory |
| 5 | Arm 3's library, fixed, with LLM-proposed seed rules per period | RQ4 | confirmatory |
| 6 | The WP1 seed library, expert-specified with AI assistance (D-002) | RQ2 | confirmatory |
| GP-conv | STGP over the conventional terminals: technical analysis and directional change (registry library `conventional`) | RQ2 (H2b) | confirmatory |
| GP-TA | STGP over technical analysis alone (`technical`), as in WP2 | H2b | secondary |
| B&H | Buy and hold | benchmark | reported |

- **H2b's comparator is GP-conv** (D-076). The plan's H2b names "conventional terminals", and the plan's conventional set is technical *and* directional-change indicators, which the registry already holds. GP-TA is kept as a secondary arm, so the WP2 pilot's comparator still has its WP4 counterpart.
- **Arm 7** (ALPHAS2- and EvoQuantLab-style re-implementations) is **not run in WP4** (D-077). Both systems would need re-implementing from papers. A faithful version would cost more than the rest of WP4's engineering, and an unfaithful one would not support a positioning claim. The paper positions against them in the related-work section and discloses the omission. Arm 7 may return as a separate study, after the confirmatory analysis.
- **Other baselines in the plan:**
  - an LLM code-evolution loop (ProFiT- or CogAlpha-style);
  - the LLQ pipeline;
  - DC-GP and ActTrade.

  These are **not part of WP4's confirmatory family**.
  - DC-GP and ActTrade are compared head to head on tier C's published datasets (§9).
  - The other two are optional secondary studies, if time and LLM budget allow after M6.

## 4. Runs

- **Runs per configuration:** 30 or 50, chosen at M2 by the rule of `docs/protocol.md` §6.4. It uses 100 runs of arm 2c on the six calibration instruments, on PL1 and PL2 training data. 30 runs are kept if the 95th percentile of |median of 30 runs − median of 100| of validation Sharpe is at most 0.05; otherwise 50 are used.
- **Seeds:** sha256 of (instruments, period, run index), as in WP2, so every arm is paired with every other on every unit (instrument, period, run).
- **Budget:** 17,750 requested evaluations per run for every GP arm (D-056). Arm 1 has no runs.
- **Maintained arms:**
  - Arms 4-grow and 4-full run their reported runs for period p on the library L(p, C), the library after period p's last maintenance cycle.
  - Arm 5 runs on arm 3's library, with the seed rules S(p, C) of its last admitted proposal.
  - The maintenance cycles' own GP runs are not reported runs. Their evaluations and tokens are reported as the method's cost (D-066).
- **Records:** as in WP2, plus the test stage's **daily net return series per (configuration, instrument, period, run)**. These are written at the test read, so the per-instrument results exist and no second read is needed (D-060).
- **Trial register:** every WP4 configuration enters `reports/configuration_register.csv` before it runs.

## 5. Maintenance on P01 → P18 → PC

- **Protocol:** WP3 protocol 1.0, unchanged:
  - C = 3 cycles per period, 3 runs per eligible instrument per cycle, FIT for the evidence and VALIDATE for gate 3;
  - arm 5's seed rules carry over between periods;
  - the library L(p, 0) = L(p−1, C), and L(P01, 0) is arm 3's library.
- **Sessions:** 19 periods × 3 cycles × 3 arms = **171 sessions**, the 162 of the WP3 protocol plus PC's 9.
  - Each is an isolated headless Claude Code session (`claude-opus-5-5`, effort high) on the PI's subscription.
  - From M4 of WP3: about 3.4 minutes and about $0.65 at API prices per session, so about 10 hours of session time and about $110 at API prices. Nothing is billed: usage beyond the plan's limit stops rather than being billed (D-068).
- **Where:** the cycles run on the Mac (D-065), at about 13 minutes per cycle with 22 instruments, scaled to the period's instrument count. That is about **45 Mac-hours** for the three arms. Only the reported runs go to CERES.
- **Order:** the periods run in sequence within each arm, because each period starts from the previous one's library. The three arms are independent and may run one after another or interleaved.
- **Every campaign** runs under a stored specification, and a resume under any other is refused (D-074).

## 6. Freeze and the single test read

1. **M5 freeze.**
   - The final rule of every reported unit is frozen: config × instrument × period × run → rule hash (arm 1: the selected strategy).
   - A freeze manifest is written with the digests of the settings, the data, the operator lock, the strategy lock, the arm-3 lock and every maintained library state and seed set (by their lineage manifests).
   - The manifest is committed to git.
   - Before the freeze, records are checked only for completeness, current digests and code version. No test-stage figure exists yet, and validation results are not used to change anything.
2. **M6 test read**, after the PI's go-ahead, recorded as a decision:
   - one pass over P01–P18 opens each period's TEST stage once, through a reader that refuses any rule not in the committed manifest;
   - it writes the daily net returns of every frozen rule;
   - a committed claim file then prevents a second read, as in WP2.
3. **A rehearsal on the validation years** (§8 of WP2) runs the same code path on VALIDATE stages before the real read.
4. **PC** has its own freeze (M7a) and read (M7b), once its data are final.

Nothing is tuned, re-run or re-selected after a test read. A defect found afterwards is reported, not fixed by re-running; this is why the external reviews come first (§10).

## 7. Primary analysis (pre-registered; completes `docs/protocol.md` §9)

- **Portfolio per arm and period:**
  - per instrument, average the daily net returns of all runs (arm 1: the selected strategy);
  - weight the period's eligible instruments equally on the union calendar, with a day without a session flat.
- **Outcome:** the annualised Sharpe of the arm's portfolio returns, concatenated over the 18 test years (P01–P18, about 4,700 business days).
- **Confirmatory comparisons** (one-sided, in the hypothesis's direction):

  | Hypothesis | Comparison | Test |
  |---|---|---|
  | H1 | 2c − 1 > 0; 2c − 2a > 0 | superiority |
  | H2a | 3 − 6 > −0.1 | non-inferiority, margin 0.1 Sharpe *(provisional)* |
  | H2b | 3 − GP-conv > 0; 6 − GP-conv > 0 | superiority |
  | H3 | 4-full − 3 > 0; 4-full − 4-grow > 0 | superiority |
  | H4 | 4-full − 5 > 0 | superiority |

  - Each comparison uses a paired stationary block bootstrap of the two portfolios' daily return differences: mean block 10 days, 10,000 resamples, a fixed seed.
  - The one-sided p-values of the 8 comparisons form **one Holm family at α = 0.05** (D-078).
  - H2a's margin of 0.1 annualised Sharpe is about half the standard error of an 18-year Sharpe. "Matches" in the plan means no worse by more than that.
- **Secondary, descriptive or with their own tests (no Holm):**
  - the mixed-effects model with period and instrument as random effects, on per-unit test Sharpe;
  - Mann–Whitney U, Cohen's d and bootstrap CIs per unit;
  - Deflated Sharpe Ratio with the register's trial counts;
  - the probability of backtest overfitting (CSCV, 16 blocks);
  - Hansen's SPA test against the best benchmark;
  - a random-entry null at each rule's trade count;
  - the cost sweep (0.5/1/2/3×, re-evaluating frozen rules);
  - lag 1;
  - inverse-volatility weights;
  - per asset class and per regime;
  - Sortino, Calmar, maximum drawdown, total return, turnover and no-trade share;
  - arms 2b and GP-TA, and B&H in every table.
- **H3's secondary claims**, smaller libraries and a smaller validation–test gap:
  - library size per period is reported for every library arm;
  - the gap is the portfolio's validation Sharpe minus its test Sharpe, per period, compared between 4-full and 3 and between 4-full and 4-grow by a paired sign test over the 18 periods;
  - validation figures are selection-biased for every arm, so the gap is compared between arms, not interpreted alone (D-060).
- **H4's matched budget:** arms 4-full and 5 have the same sessions, effort and tool limits per cycle (WP3 protocol §2). Their tokens, GP evaluations and wall-clock times are reported side by side.
- **Library-lifecycle metrics** (plan): operators proposed, admitted, retired and refined per cycle, reuse across assets and periods, library size over time, surviving domains, and cap hits (D-067).

## 8. Compute

| Part | Where | Size | Estimate |
|---|---|---|---|
| Runs study (M2) | CERES or Mac | 100 runs × 6 instruments × 2 periods, arm 2c | about 15 core-hours |
| Maintenance (M3) | Mac | 171 sessions; 171 cycles × about 80 runs each | about 45 Mac-hours plus about 10 h of sessions |
| Reported runs (M4) | CERES | 10 GP arms × 496 pairs × 30 runs = 148,800 runs (PC adds about 9,300) | about 1,900 core-hours at 30 runs (about 3,200 at 50); 1.5–3 days at 60 concurrent tasks |
| Test read (M6) | Mac | one pass over every frozen rule | hours |

The figures scale the go/no-go's measured cost: about 13 core-hours a period for five GP arms, 22 instruments and 10 runs. Arm 3's runs took about 35 s each on the Mac in WP3. M4 uses CERES under the existing arrangement (D-046). Running it is a **PI** go-ahead.

## 9. Tiers B and C (not in the confirmatory family)

- **Tier B** (about 100 stocks) needs a survivorship-free source from the PI (D-015, D-031 item 10). It is a separate campaign under this protocol, with its own freeze and read, and it is reported as a breadth study. If its data are not available by the end of M4, the paper reports tier A only and says so.
- **Tier C** (the Essex DC-GP and ActTrade datasets) needs the PI to copy the datasets into `tierC/` (D-016). It is a head-to-head comparison with the published results on the published splits, for the confirmatory arms that can run on its data.

## 10. Milestones

| | Milestone | Needs |
|---|---|---|
| M0 | Protocol 1.0, after the external reviews of the WP3 fixes and of this protocol's code | PI: data choice (§2); reviews |
| M1 | Code: lift the WP2 data cap to stage sealing (decision), the WP4 campaign plans, per-instrument test series, the freeze-checked test reader, the PC period, the GP-conv configuration. Leakage tests for each. | code; **PI decision** recorded to lift the cap |
| M2 | Runs-per-configuration study (§4) | runs (CERES or Mac) |
| M3 | Maintenance campaign: arms 4-grow, 4-full and 5 over P01 → P18 → PC | **PI go-ahead** (171 sessions) |
| M4 | Reported runs, every arm, P01–P18 and PC | **PI go-ahead** (CERES) |
| M5 | Freeze manifest for P01–P18, committed | code |
| M6 | Validation-year rehearsal, then the single test read of P01–P18; primary analysis | **PI go-ahead**, recorded as a decision |
| M7 | PC freeze and test read, when its data are final | **PI go-ahead** |

The plan puts WP4 at 15 Mar – 14 May 2027. Code and the runs study can start now; nothing in M1–M2 touches a P01–P18 test year.

## 11. Change log

- **3 Nov 2026, draft 0.1:** written (engineer, under D-042/D-061). Decisions D-075–D-079.
