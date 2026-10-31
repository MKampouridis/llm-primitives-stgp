# WP1 smoke test, calibration and compute/disk projections

Generated from code `c41f2dd`. All runs use P01 training data (fit 2005-07..2007-06) and its validation year (2007-07..2008-06) only; P01's test year is sealed. Machine: Apple M1 (4 performance + 4 efficiency cores), 16 GB RAM, one BLAS/numba thread per run.

## Smoke test (as specified)

S&P 500 and EUR/USD, P01, seed library (28 cross-domain operators + core), population 200 x 10 generations, 2 seeds per asset, 4 parallel workers: **4 runs in 29 s**.

| Asset | Seed | Wall-clock (s) | Requested evals | Unique evals | ms / requested eval | ms / unique eval | Unique eval ms p50 / p90 / p99 | Cold (gen 0) / warm ms per unique eval | Subtree-cache hit rate | Peak RSS (MB) | Run record (KB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 1 | 25.8 | 2,200 | 915 | 11.2 | 25.4 | 1.5 / 55.9 / 482 | 72 / 12.4 | 0.55 | 221 | 30 |
| EURUSD | 2 | 24.5 | 2,200 | 818 | 10.6 | 26.9 | 4.6 / 53.6 / 361 | 69 / 13.3 | 0.53 | 222 | 30 |
| SPX | 1 | 23.8 | 2,200 | 984 | 10.5 | 21.5 | 2.2 / 47.1 / 330 | 71 / 8.9 | 0.55 | 224 | 30 |
| SPX | 2 | 23.5 | 2,200 | 881 | 10.2 | 23.4 | 3.8 / 48.6 / 357 | 68 / 10.4 | 0.53 | 225 | 30 |

- **Runtime per fitness evaluation:** 10.6 ms per requested evaluation on average (24.3 ms per unique, i.e. not-yet-seen, rule). A unique evaluation costs ~70 ms while the subtree cache is cold (generation 0) and ~9-13 ms once warm; requested evaluations are cheaper because repeated rules are not re-evaluated.
- **Disk use of the run:** 119 KB of run records for the 4 runs (~30 KB per run: summaries and the hall of fame only, no populations). The subtree cache is in memory only; the numba compilation cache is 5.8 MB in the local clone (git-ignored, outside Box).

## Calibration

- **Conventional (TA/DC) library**, same configuration: 3.1 ms per requested evaluation, i.e. 0.30x the cross-domain library.
- **Single worker** (smoke size, alone): 10.4 ms per requested evaluation, peak RSS 254 MB.
- **6 concurrent workers:** 17.1 ms per requested evaluation each, i.e. a throughput speed-up of 3.7x on this laptop (4 of the 8 cores are efficiency cores); 223 MB peak RSS per worker (subtree cache ~26 MB).
- **Full-budget run** (SPX, population 500 x 50 generations = 25,500 requested, 4,393 unique evaluations): 1.7 min, 3.9 ms per requested and 19.2 ms per unique evaluation, peak RSS 254 MB, record 50 KB.

| Generation | New unique evals | ms per unique eval | Mean nodes (both trees) | Mean weighted size | Cache hit rate | Elapsed (s) |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 500 | 53.3 | 22.7 | 7.3 | 0.43 | 27 |
| 1 | 358 | 4.5 | 21.4 | 6.6 | 0.49 | 29 |
| 10 | 113 | 15.7 | 17.6 | 4.5 | 0.60 | 56 |
| 25 | 34 | 17.8 | 15.1 | 4.0 | 0.61 | 74 |
| 50 | 25 | 9.9 | 15.1 | 4.1 | 0.61 | 100 |

Slowest operator calls (P01 FIT arrays of 1006 bars; each subtree is computed once per run thanks to memoisation):

| Contract | Parameters | ms per call |
|---|---|---:|
| `sinkhorn_divergence@1` | {'epsilon': 0.25} | 430.7 |
| `p_variation@1` | {'window': 120, 'pvar': 3.0} | 159.7 |
| `sinkhorn_divergence@1` | {'epsilon': 1.0} | 100.2 |
| `past_hist@1` | {'window': 120} | 43.0 |
| `generalized_hurst@1` | {'window': 252, 'q': 2.0} | 32.6 |
| `transport_asymmetry@1` | {'window': 252} | 31.8 |
| `rolling_hist@1` | {'window': 120} | 30.0 |
| `ssa_trend_share@1` | {'window': 252} | 26.8 |
| `quantile_regime@1` | {'window': 252} | 20.9 |
| `past_hist@1` | {'window': 10} | 20.8 |
| `dfa@1` | {'window': 252} | 20.2 |
| `rolling_hist@1` | {'window': 10} | 18.6 |

Median ms per call by domain: core 0.26; data 0.00; directional_change 0.58; fractal 4.66; information_geometry 0.37; information_theory 0.72; optimal_transport 11.95; rough_paths 1.11; spectral 1.27; statistical_physics 1.54; technical 0.18

## Projections for the full design

**Design counted.** The GP configurations, each run on every eligible (instrument, period) pair x 30 seeds:

- Arm 2a: whole LLM strategies as Boolean terminals (cost class: terminal)
- Arm 2b: their signal series as terminals (cost class: terminal)
- Arm 2c: parameterised operators (cost class: cross)
- Arm 3: frozen LLM-authored library (cost class: cross)
- Arm 4-grow: maintained, growth only (cost class: cross, +5% evaluations for maintenance/gates)
- Arm 4-full: maintained, grow/prune/refine (cost class: cross, +5% evaluations for maintenance/gates)
- Arm 5: fixed grammar + LLM tree operators (cost class: cross)
- Arm 6: expert library (this seed library) (cost class: cross)
- Arm 7a: ALPHAS2-style distillation (cost class: cross, +5% evaluations for maintenance/gates)
- Arm 7b: EvoQuantLab-style terminal lifecycle (cost class: terminal, +5% evaluations for maintenance/gates)
- Baseline: GP with TA terminals (cost class: terminal)
- Baseline: DC-GP (cost class: terminal)
- Baseline: ActTrade (cost class: terminal)
- Baseline: LLM code-variation loop (cost class: cross)

Selection-only items need negligible compute: Arm 1: best of ~30 whole LLM strategies; LLQ pipeline (portfolio GA); Buy-and-hold.

**Assumptions and measured inputs.**

- Eligible Tier A pairs: 496 (467 business-day, 29 crypto); periods P01-P18.
- Cost per requested evaluation: central 3.9 ms (full-budget run, caches warm), high 10.4 ms (small budget, cold caches); conventional/terminal-only configurations x0.30; crypto x1.22 (longer fit windows).
- Sandboxes always hold 504 warm-up + fit bars, so the cost per evaluation does not grow across periods.
- Laptop: measured 3.7x throughput with 6 workers. Cluster nodes: per-core speed of one M1 performance core, 90% parallel efficiency (assumption).
- Disk: run records of 30 KB at 11 generations plus 0.5 KB per further generation (population 500); gzip would cut this ~5x.
- Tier B option 1: 100 stocks x 18 periods (upper bound; delisted names shorten later periods). Option 2: 4 markets x 18 periods, each evaluation scores 25 stocks (25x the cost per evaluation, 25x fewer runs).
- Not included: LLM tokens and API time (WP3), re-running arms for the cost sweep (re-evaluating fixed rules at 0.5/1/2/3x costs is negligible; re-evolving them would multiply the affected rows by 4).

| Scenario | Evaluations / run | Runs | Evaluations | Core-hours (central / high) | Laptop days (central / high) | 64-core node days | 128-core node days | Disk for run records (GB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tier A (31 instruments) | 10,000 | 208,320 | 2.11e+09 | 1,631 / 4,340 | 18.6 / 49.4 | 1.2 | 0.6 | 7.31 |
| Tier A (31 instruments) | 25,000 | 208,320 | 5.28e+09 | 4,079 / 10,849 | 46.4 / 123.4 | 3.0 | 1.5 | 10.48 |
| Tier A (31 instruments) | 50,000 | 208,320 | 1.06e+10 | 8,157 / 21,699 | 92.8 / 246.8 | 5.9 | 3.0 | 15.78 |
| Tier B option 1: one rule per stock | 10,000 | 756,000 | 7.67e+09 | 5,844 / 15,545 | 66.5 / 176.8 | 4.2 | 2.1 | 26.52 |
| Tier B option 1: one rule per stock | 25,000 | 756,000 | 1.92e+10 | 14,610 / 38,863 | 166.2 / 442.1 | 10.6 | 5.3 | 38.05 |
| Tier B option 1: one rule per stock | 50,000 | 756,000 | 3.83e+10 | 29,220 / 77,727 | 332.4 / 884.1 | 21.1 | 10.6 | 57.26 |
| Tier B option 2: one rule per market, pooled | 10,000 | 30,240 | 3.07e+08 | 5,844 / 15,545 | 66.5 / 176.8 | 4.2 | 2.1 | 1.06 |
| Tier B option 2: one rule per market, pooled | 25,000 | 30,240 | 7.67e+08 | 14,610 / 38,863 | 166.2 / 442.1 | 10.6 | 5.3 | 1.52 |
| Tier B option 2: one rule per market, pooled | 50,000 | 30,240 | 1.53e+09 | 29,220 / 77,727 | 332.4 / 884.1 | 21.1 | 10.6 | 2.29 |

**Tier B options compared.** Total compute is about the same (both evaluate 1,800 stock-periods per configuration and seed), but option 2 has 25x fewer runs, 25x longer runs, 25x fewer run records and 25x fewer LLM maintenance cycles in WP3. Memory per pooled run grows with the number of stocks: keeping the per-stock subtree cache at its current size (~26 MB) needs ~0.9 GB per pooled run, so about 16 concurrent pooled runs fit in 16 GB (set `cache_mb` accordingly, it is 512 MB per run by default).

**Sensitivity to the budget definition (open for WP2).** In the full-budget run only 4,393 of 25,500 requested evaluations were new rules: the population converges and repeated rules are served from the fitness cache, which is why the central cost is low. If the matched budget is defined in unique evaluations, or WP2 adds diversity control so that most evaluations are new rules, the cost per budget unit approaches the per-unique cost (19.2 ms, ~4.9x the central figure): multiply the central core-hours accordingly. Projected disk use also matters for storage: 10-60 GB of uncompressed run records would not fit comfortably on this laptop (22 GB free) and should go, compressed and sharded, to cluster storage (WP4).
