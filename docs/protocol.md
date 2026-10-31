# WP2 protocol: whole LLM strategies, STGP arms 1–2 and the pilot go/no-go

**Status: version 1.0 (31 Oct 2026).** Written before any strategy generation, calibration or
pilot run. The PI delegated scientific decisions to the engineer (D-042); the items that the draft
left to the PI were decided in D-041. Every later change is logged in §11 (date, reason, who
decided) and reported in the paper. The protocol is frozen when the pilot ends. Decisions referred
to as D-xxx are in `docs/decisions.md`.

## 1. Purpose

WP2 produces a fresh set of whole LLM-written strategies under a fixed protocol and decides the
February go/no-go: **is primitive-level STGP (arm 2c) competitive with selecting among whole LLM
strategies (arm 1)?** It also calibrates the GP and fitness settings that all arms share.

## 2. Data, periods and horizons

- **Tier A** daily bars, close-only terminals, per-instrument costs (WP1 data layer, D-008–D-017).
- **Primary periods P01–P18** (fit 2 y + validation 1 y, test 1 y; P01 fit from 2005-07-01):
  untouched in WP2.
- **Pilot periods** (D-034), the same structure, before P01:

  | Period | Fit | Validation | Test |
  |---|---|---|---|
  | PL1 | 2003-07-01 – 2005-06-30 | 2005-07-01 – 2006-06-30 | 2006-07-01 – 2007-06-30 |
  | PL2 | 2004-07-01 – 2006-06-30 | 2006-07-01 – 2007-06-30 | 2007-07-01 – 2008-06-30 |

  22 instruments are eligible in both (504 warm-up bars, ≥ 95% session coverage): SPX, NDX, SMI,
  DAX, CAC, UKX, NKY, HSI, KOSPI, AS51; EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD,
  EURGBP; NATGAS, GOLD, SILVER, COPPER.
- **Development window** for strategy generation (D-036): dev-fit 1995-07-01 – 2003-06-30
  (21 instruments with ≥ 750 bars: the 10 indices, 8 FX pairs, WTI, Brent and natural gas);
  dev-holdout 2003-07-01 – 2005-06-30 (24 instruments). It ends before every pilot validation
  year.
- **Data cap:** no modelling code reads any bar on or after **2008-07-01** in WP2. This is
  enforced in code: the capped store, `Sandbox.open`, and the pilot-only test stage (D-034).
- **Post-cutoff window** (D-036): all LLM work uses `claude-opus-5-5`, whose training-data cutoff
  is June 2026. The post-cutoff test runs from 2026-07-01 to the latest data at the WP4 freeze and
  is reported separately. P18 (2025-07 to 2026-06) is an ordinary period.

## 3. Arms run in WP2 (D-037)

| Arm | Rule source | Final rule per (instrument, period, run) |
|---|---|---|
| 1 | The 28 whole strategies, unchanged | The strategy with the best validation fitness (deterministic; no runs) |
| 2a | STGP over each strategy's entry and exit (56 Bool terminals) with And/Or/Not | Best validation fitness in the hall of fame |
| 2b | STGP over the strategies' signals at their own parameters (Real terminals) plus core glue (adaptive thresholds, comparators, logic, regimes) | as 2a |
| 2c | STGP over the strategies' signals as typed operators whose grid parameters the GP chooses, on the data terminals, plus the same glue | as 2a |
| 6 | STGP over the WP1 seed library (expert-specified, AI-assisted; D-002) | as 2a |
| GP-TA | STGP over 23 technical-analysis terminals plus core glue | as 2a |
| B&H | Buy and hold | — |

Arms 1, 2a, 2b and 2c share the same mathematics; they differ only in granularity (RQ1).

## 4. Strategy generation (D-035)

- **Author:** `claude-opus-5-5` through headless Claude Code (`claude -p`, version recorded,
  auto-update off), on the PI's subscription (no API credits), effort `high`. No fallback model;
  a different model id in the transcript invalidates the session, and a session cut short (usage
  limit, crash) is resumed, never accepted half-way.
- **Number:** 28 strategies, 4 for each of the 7 domains of the research plan. The 4 sessions
  of a domain run in order; each later brief lists the names and hypotheses of the earlier
  accepted strategies of that domain, which the new one must differ from.
- **Isolation**, verified by a pre-flight session (§11):
  - each session runs in a fresh, neutrally named folder outside the repository and Box, holding
    only `BRIEF.md` and `strategy_api.py`;
  - its tools are Read, Write, Edit, Glob and Grep, confined to that folder (`--restricted`),
    plus two MCP tools from our server: `check` and `backtest`;
  - it has no shell, no web access, no other MCP servers, no skills and none of the user's
    settings, CLAUDE.md or memory;
  - it never sees prices, dates, instrument names, our code, the research plan or the WP1
    operators.
  - *Disclosure:* Claude Code attaches the account e-mail address to the context.
- **Brief:** `src/lpstgp/strategies/prompts/brief.md` (original wording; no text from LLQ's
  prompt), rendered per slot, with its sha256 archived. It states:
  - the domain scope and the contract;
  - the objective, which uses the same fitness F as the GP (median across instruments);
  - the budget: 40 backtests and up to 100 free checks (a resumed session keeps its count);
  - exploration: at least 3 distinct hypotheses within the first 10 backtests;
  - stopping: at the budget, or after 10 backtests without improvement once 20 are used.
- **Contract and gates** (D-038):
  - **Contract:** 1–4 signals with parameters on the GP's grids, plus a stateless rule giving
    entry/exit in {0, 1, NaN}. Signals are not shifted; the harness applies the execution lag.
  - **Source policy:** numpy, scipy and math only; no I/O, randomness or reflection.
  - **Behaviour:** deterministic (also across processes and thread counts); prefix-invariant
    under adversarial appends; within the declared lookback (≤ 504 bars); shift-invariant for
    price inputs.
  - **On development data:** finite, and with entries and exits firing on most instruments.
  - **Isolation of the code:** the agent's code runs only in a `sandbox-exec` subprocess with no
    network and no writes outside its job folder.
- **Acceptance:**
  - The final file must pass all gates and the cross-process determinism check.
  - A failure gets one repair turn (same session, gate report as the prompt); a second failure
    re-runs the slot once in a fresh session.
  - Every failure and repair is counted.
- **Archive** (per session):
  - the stream-json transcript and Claude Code's own transcript;
  - every submitted version with its check or backtest result;
  - the brief and its hash;
  - per-message model ids, token usage and estimated cost;
  - the dev-fit and dev-holdout scores of the final file. The dev-holdout score is never shown to
    the agent.
- **Freeze:** accepted files are copied verbatim to `src/lpstgp/strategies/generated/`, hashed
  into `strategies.lock.toml` with their provenance, and catalogued in `docs/strategies.md`.
  Development-window backtests are trials on pre-sample data only; they are reported, not counted
  as trials on pilot or primary data.

## 5. Elements fixed for every arm

- **Costs:** per-instrument one-way bps from the universe configuration, multiplier 1. The cost
  sweep (0.5/1/2/3×) re-evaluates frozen rules (WP4).
- **Execution (D-041):** primary lag 2. A condition true at the close of bar *t* changes the
  position at the close of bar *t+1*. The pre-registered robustness check is lag 1, trading at
  the signal bar's own close.
  - *Why:* the data are close-only and include prices that cannot be traded at (ECB fixings, EIA
    assessments, cash index levels).
  - It matches the convention of LLQ's prompt (compute at the close, execute on the next bar).
  - It is conservative for every arm alike.
- **Fitness F:**
  - per instrument and half-year segment: median net Sharpe − λ_dd · median(MDD/σ) − λ_to ·
    median turnover;
  - a segment with fewer than 10 bars in the market scores Sharpe 0;
  - a rule that enters fewer than 2 times per year of data (rounded: 4 in a 2-year fit, 2 in a
    validation year), or never trades, scores −1 (D-041; fixed a priori, not tuned);
  - pooled over instruments by the mean, minus λ_size · weighted size.
  - The current λ values (0.5, 0.005, 0.01) are placeholders until §6.3.
- **Final selection:** the hall-of-fame member (10, deduplicated by signals) with the best
  validation F; arm 1 uses the same score.
- **Seeds:** sha256 of (instruments, period, run index), never of the arm, so arms are paired.
- **Runs:** 10 per configuration, instrument and pilot period. WP4 uses 30 or 50 by the rule in
  §6.4.
- **Records:** one JSON record per run, holding:
  - settings, data and library digests, and the sandbox access log;
  - per-generation aggregates, plus validation checkpoints every 10 generations that are never
    used for selection;
  - the hall of fame.
- **Campaigns:** each campaign is planned with frozen digests, resumed safely, and collected into
  `runs.parquet`. Every configuration ever planned enters `reports/configuration_register.csv`.

## 6. Calibration (PL1 and PL2 FIT/VALIDATE only, before any pilot test read)

1. **GP parameters, at equal budget.**
   - Candidates: population {250, 500, 1000} × tournament {3, 5}, each with 50,000 requested
     evaluations.
   - Runs: arms 2c and 6, 6 instruments (2 indices, 2 FX, 2 commodities, fixed in advance),
     10 runs each, on PL1.
   - Convergence of a run: the first generation whose best fit F reaches 99% of the run's total
     rise. A candidate's generations are the median convergence generation, rounded up to 10.
   - **Choice:** the cheapest candidate whose median validation F is within 0.05 of the best.
2. **Budget unit.** Budget in unique evaluations if the median unique share of evaluations differs
   by more than 2× between arms in step 1; otherwise in requested evaluations.
3. **Fitness weights.** The minimum activity is fixed in §5. Keep λ unless, on PL1/PL2
   validation, more than 25% of final rules never trade, or the median turnover exceeds 50
   position changes a year. In that case, raise λ_to stepwise (×2, ×4) until both conditions
   hold.
4. **Runs per configuration for WP4**, run at the start of WP4 on PL1/PL2 training data, not in
   WP2. Run 100 runs of arm 2c on the 6 instruments. Keep 30 runs if the 95th percentile of
   |median of 30 runs − median of 100| of validation Sharpe is at most 0.05; otherwise use 50.

Every candidate is a registered configuration. The chosen values are recorded as decisions and
written to `config/settings.toml` before the freeze.

## 7. Freeze before the pilot test read

After calibration, all final rules of the go/no-go campaign (config × instrument × period × run →
rule hash) and the digests of settings, data, operator lock and strategy lock are written to a
freeze manifest, `reports/wp2/freeze_manifest.json`. The manifest is **committed to git**. The
pilot test stage refuses to open without a committed manifest (`Sandbox.open_pilot_test`), and
each evaluated rule must be listed in it.

## 8. Go/no-go (PL1 and PL2 test years, read once)

- **Portfolio:**
  - per instrument, average the daily net returns of all 10 runs (arm 1: the selected strategy);
  - weight the 22 instruments equally on the union calendar, with a day without a session flat;
  - net of costs, at the execution lag of §5.
- **Measure:** the portfolio Sharpe of each arm over the two pilot test years pooled (504
  business days), and per year.
- **Rule (D-041): GO if the paired difference in pooled portfolio Sharpe, arm 2c − arm 1, is
  at least −0.2.** This is a non-inferiority rule on the point estimate.
  - The gate asks whether primitives are competitive before the LLM maintenance arms are built.
    It is not the confirmatory test.
  - A one-year Sharpe has a standard error of about 1, so a per-year rule would mostly track
    noise; pooling halves the variance.
- **Also reported:**
  - 2a, 2b, 6, GP-TA and B&H;
  - paired stationary-bootstrap confidence intervals for 2c − 1 and the other differences;
  - per-instrument results;
  - validation–test gaps.
- **On NO-GO:** a NO-GO goes to the PI for a decision on reframing (the plan's risk table). It is
  never followed by tuning on the pilot test years.

## 9. WP4 primary analysis (pre-registered here; finalised before WP4)

- **Outcome:** out-of-sample net Sharpe of the equal-weight portfolio over the P01–P18 test
  years, with the same aggregation as §8. The post-cutoff window is reported separately.
- **Confirmatory test (D-041):** for each hypothesis's pairwise comparisons, a paired
  stationary block bootstrap of daily portfolio returns (mean block 10 days, 10,000 resamples),
  with Holm across the family.
  - This departs from the plan, which names Mann–Whitney U with Holm. The reason: units sharing a
    market year are not independent (D-033), so per-unit Mann–Whitney tests, Cohen's d and
    bootstrap CIs are reported descriptively.
- **Model:** a mixed-effects model with period and instrument random effects.
- **Secondary:**
  - Deflated Sharpe Ratio, with trial counts from the configuration register;
  - probability of backtest overfitting (CSCV, 16 blocks);
  - Hansen's SPA test against the best benchmark;
  - a random-entry null (1,000 draws at the rule's trade count);
  - the cost sweep.

## 10. Deviations

Any departure from this protocol is recorded in `docs/decisions.md` and §11 before it takes
effect. Departures after the pilot test read are reported in the paper with their reasons.
Configurations tried and dropped stay in the register.

## 11. Change log

- **31 Oct 2026, draft 0.1:** written (engineer), from the WP2 plan approved by the PI and
  D-033–D-040.
- **31 Oct 2026, version 1.0:** the PI delegated scientific decisions (D-042). The draft's
  open items were decided (D-041): lag 2 primary; at least 2 entries per year; effort high;
  40 backtests; 10 pilot runs; go/no-go as pooled non-inferiority (δ = 0.2); the paired
  portfolio bootstrap as the confirmatory test; the runs-per-configuration study moved to WP4.
  Sessions cut short are resumed with their budget kept, and a model mismatch invalidates a
  session.
- **31 Oct 2026, isolation pre-flight:** results archived in
  `results/wp2/preflight/20261031T092025Z/`.
  - The session's tools were exactly Read, Write, Edit, Glob, Grep and the two MCP tools.
  - Reads outside the folder were refused.
  - There was no shell or web tool, and no CLAUDE.md, memory or skills were loaded.
  - The model was `claude-opus-5-5` throughout.
