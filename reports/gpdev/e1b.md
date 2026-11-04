# GP development E1b: pooled, 6-year training windows

Pass marks (fixed before the runs, D-092): median evolution gain in validation Sharpe >= 0.1 with one-sided Wilcoxon p < 0.05 over runs; median Spearman rho (training fitness, validation Sharpe) >= 0.1. Validation years 2005-06, 2006-07 and 2007-08; no test data.

| variant | cells | runs | fit Sharpe | val Sharpe gen 0 | val Sharpe last | gain (p) | rho | trades (fit) | exposure fit / val | passes |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|
| e1b-2c/pooled | 4 | 40 | 0.46 | 0.47 | 0.36 | -0.02 (0.540) | -0.07 | 22 | 0.48 / 0.50 | no |
| e1b-TA/pooled | 4 | 40 | 0.45 | 0.42 | 0.50 | +0.03 (0.064) | -0.04 | 37 | 0.36 / 0.39 | no |
| e1-2c-comp/pooled-2y | 4 | 40 | 1.51 | 0.67 | 0.59 | -0.03 (0.728) | -0.30 | 8 | 0.49 / 0.55 | no |
| e1-TA-comp/pooled-2y | 4 | 40 | 1.40 | 0.77 | 0.71 | -0.02 (0.607) | +0.32 | 12 | 0.52 / 0.56 | no |

**Decision (arm 2c):** no variant passes: stop and rethink before any larger run
