# WP4 runs-per-configuration study (protocol.md §6.4)

Arm 2c, 100 runs on each of 12 (instrument, period) cells (PL1 and PL2 training data; validation Sharpe of each run's selected rule).

- 95th percentile of |median of 30 − median of 100|: **0.2539** (tolerance 0.05).
- **Runs per configuration in WP4: 50.**

| cell | 95th percentile | median |
|---|---:|---:|
| EURUSD/PL1 | 0.2502 | 0.0597 |
| EURUSD/PL2 | 0.1648 | 0.0521 |
| GOLD/PL1 | 0.3523 | 0.1180 |
| GOLD/PL2 | 0.1317 | 0.0402 |
| NATGAS/PL1 | 0.3080 | 0.1310 |
| NATGAS/PL2 | 0.2360 | 0.1126 |
| NKY/PL1 | 0.3083 | 0.1390 |
| NKY/PL2 | 0.1725 | 0.0595 |
| SPX/PL1 | 0.2052 | 0.0538 |
| SPX/PL2 | 0.2080 | 0.0742 |
| USDJPY/PL1 | 0.2188 | 0.0817 |
| USDJPY/PL2 | 0.2892 | 0.1068 |

## Notes

- The study ran on the Mac (D-048: one campaign, one machine), from 16:39 to about 18:30 GMT on 3 Nov 2026, because CERES's queue had been stalled for hours. It used FIT and VALIDATE stages of PL1 and PL2 only.
- The rule is the pre-registered one (protocol.md §6.4) and is applied as written. The tolerance of 0.05 is far from met: run-to-run spread of validation Sharpe is large (median interquartile range across runs, per cell: 0.87).
- *For information only* (not part of the rule): with subsets of 50 runs, the same 95th percentile is 0.18 (median 0.05), against 0.26 (median 0.08) with 30. Fifty runs narrow the per-cell uncertainty by about a third. The confirmatory test works on portfolios that average all runs per instrument over 18 test years (protocol_wp4 §7), so this spread mainly affects per-unit secondary analyses.
