# WP1 summary — operator library, data layer and evaluation harness

31 October 2026. Code: private GitHub repository `MKampouridis/llm-primitives-stgp` (local clone `~/code/llm-primitives-stgp`). Every choice is recorded in `docs/decisions.md` (D-001 to D-031). No LLM calls were made, and no test-period data were inspected or used: all modelling computation ran on FIT/VALIDATE sandboxes.

## What was built

| Component | Summary |
|---|---|
| Repository | uv project (uv-managed Python 3.12, locked dependencies), ruff, pytest. GitHub Actions runs lint, format, hygiene and the synthetic-data test suite on every push. `.gitignore` plus a hygiene check (pre-commit hook and CI) keep data, large files and secrets out of git. |
| Data layer | Schema v1: raw OHLCV + dividend/split events in zstd Parquet with month row groups. Adjustment is causal, at read time. Structural, row-local validation, so the build is causal (tested). Tier A pilot download from free sources (Yahoo, ECB, EIA, Bitstamp, Coinbase) with an append-only, checksummed manifest. Tier B: survivorship-free selection rule and vendor interface. Tier C: manifest-driven loader. Per-tier data reports. |
| Splits and leakage | 18 rolling periods (fit 2 y + validation 1 y, test 1 y; July anchor, P18 = the provisional post-cutoff year). The `Sandbox` gives modelling code exactly 504 warm-up bars plus data before the stage horizon; the test stage is sealed. Enforced by poisoned-future canaries, FIT-prefix-of-VALIDATE tests, a static import policy, causal-build and invariance tests, and an access log in every run record. |
| Operator contract | Name, immutable version, semantic types (Series, Path, Hist, Real, Bool, Regime), parameters on legal grids, lookback and earliest availability, missing-data policy, invariances, LaTeX definition with references, reference test, provenance, implementation. One file per version; a version lock (code + semantic fingerprint) makes locked contracts immutable. |
| Admission gates | Compiles + source policy; type-correct; finite and non-constant (synthetic, and real P01 data); deterministic (also in a fresh process with other thread counts); prefix-invariant bit for bit under adversarial appends; exact declared lookback; declared invariances. |
| Seed library (arm 6) | 28 cross-domain operators, 4 per domain (information theory, information geometry, optimal transport, rough paths, fractal analysis, statistical physics, spectral methods). 17 core operators: histogram/path constructors, adaptive thresholds (rolling percentile, mean + k·sd and fused versions), comparators, Kleene logic, regimes. 3 data terminals. Separately, 23 TA and 20 directional-change terminals. 91 contracts in total, frozen, documented in `docs/operators.md`, each with a reference test. |
| STGP | DEAP typed primitive set with our own lookback-aware generator, homologous crossover, four mutation kinds, tournament selection, elitism and a signal-deduplicated hall of fame. Entry/exit Boolean rule pairs, long-only. Robustness-composite fitness on training data (median half-year Sharpe, scale-free drawdown, turnover, weighted size). Pooled fitness over several instruments is supported. Seeded runs are reproducible across processes. |
| Backtester | Vectorised, long-only, one-bar execution shift (lag configurable), per-asset buy/sell costs with a multiplier for the sensitivity sweep, batch mode, standard metrics. |
| Smoke test and projections | As requested, plus calibration runs (see below); reports in this folder. |

## Test results

- **1,241 tests pass locally** (with real data); **1,133 pass in CI** (synthetic data only). Lint and format are clean, and CI has been green on every push.
- **By area:** gates 1,059 (91 contracts × sampled parameters), operator reference tests 77, data 47, GP 23, backtest 10, leakage 9, splits 6, repository hygiene 8.
- **References matched:** scipy, antropy, ordpy, scikit-learn, POT, roughpy, nolds, statsmodels, PyWavelets, ta/pandas, numerical quadrature, brute-force p-variation, and an independent directional-change event loop. Recovery tests use fractional Brownian motion, Pareto tails and AR processes.

## Data reports (availability counts only)

- **Tier A** (`data_tierA.md`):
  - 31/31 instruments: 10 equity indices, 8 FX, 6 commodities, 2 bonds, 5 crypto.
  - 55 raw series (alternates included), 38.8 MB.
  - **496 eligible (instrument, period) pairs**: 25 instruments in P01, rising to 31 from P15. Crypto enters from P09 (BTC) or P14/P15.
  - Coverage is ≥ 97% for all but WTI (92.3%: real EIA gaps in 2003–06 and 2011, so eligible P02–P18 only) and Brent (90.4% against the London calendar; eligible P01–P18).
  - One invalid bar: the negative WTI print of 2020-04-20.
  - Yahoo's metal futures have many inconsistent highs/lows (close kept) and unadjusted roll gaps.
- **Tier B** (`data_tierB.md`): interface and selection rule only; a survivorship-free vendor is still needed.
- **Tier C** (`data_tierC.md`): `tierC/` is empty.
- **Changes from the plan, forced by free-source availability:**
  - Stooq is blocked and FRED's key-less endpoint fails for scripts, so FX and energy come from the ECB and EIA.
  - SMI replaces the Euro Stoxx 50 (Yahoo's history starts only in 2007).
  - No free Bund history exists, so there are 2 bonds.
  - BCH replaces SOL (SOL's history is too short).

## Smoke test, calibration and projections (`smoke_and_projections.md`)

- **Smoke test:** S&P 500 and EUR/USD, P01, population 200 × 10 generations, 2 seeds each. 4 runs in 29 s on 4 workers.
  - **Runtime per fitness evaluation:** 10.6 ms per requested evaluation; 24 ms per new rule (about 70 ms with a cold cache, 9–13 ms warm).
  - **Disk:** 30 KB per run record, 119 KB in total, plus a 5.8 MB numba cache. Peak memory is about 225 MB per run.
- **Calibration:**
  - The conventional TA/DC library costs 0.30× the cross-domain one.
  - 6 workers give a 3.7× speed-up on the M1.
  - The full-budget run (500 × 50) took 1.7 min: 3.9 ms per requested evaluation. Only 17% of evaluations were new rules, because the population converges.
  - Sinkhorn divergence is the costliest operator (0.1–0.4 s per call).
- **Projections**, central cost, 14 GP configurations × eligible pairs × 30 seeds:

  | Scenario | Evaluations per run | Core-hours | Laptop days | 128-core node days | Run records |
  |---|---:|---:|---:|---:|---:|
  | Tier A | 25,000 | 4,079 | 46 | 1.5 | 10.5 GB |
  | Tier A | 50,000 | 8,157 | 93 | 3.0 | 15.8 GB |
  | Tier B, per stock | 25,000 | 14,610 | 166 | 5.3 | 38 GB |
  | Tier B, pooled per market | 25,000 | 14,610 | 166 | 5.3 | 1.5 GB |

  - The high (cold-cache) cost is ×2.7. A unique-evaluation budget would be ×4.9.
  - The two Tier B options need the same compute, but pooling means 25× fewer runs, records and WP3 maintenance cycles.

## Open questions for WP2 (details in D-031)

1. Pilot periods for calibration and the go/no-go (proposal P01–P02, excluded from the primary outcome).
2. Primary execution lag (1 or 2).
3. Final-rule selection on validation or on fit.
4. Budget unit: requested or unique evaluations, and diversity control.
5. Fitness weights, or NSGA-II.
6. Cost sweep: re-evaluate or re-evolve.
7. Portfolio aggregation across calendars.
8. Arm 3 protocol (free authoring or arm 6's specs), the LLM(s) and the post-cutoff year.
9. Source of arm 2c's operators.
10. Tier B vendor, selection mode, Japan/Asia composition, and per-stock vs pooled rules.
11. Vendor futures for WP4.
12. A cluster allocation.
13. Sinkhorn's cost.
14. PI review of the arm-6 contracts (`docs/arm6_review.md`) and updating the plan's Method §1 wording.
15. Tier C datasets.
16. Licence.
