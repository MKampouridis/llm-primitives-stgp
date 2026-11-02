# WP2 pilot go/no-go (protocol §8)

Freeze manifest committed in 66c26deb1770; test years 2006-07..2008-06 read once; 22 instruments; equal-weight portfolios of all runs.

**Decision: GO** (GO if Sharpe(2c) - Sharpe(1), pooled, >= -0.2; difference +0.313).

| arm | pooled Sharpe | PL1 test | PL2 test |
|---|---:|---:|---:|
| 1 | 0.374 | 1.695 | -0.602 |
| 2a | 0.694 | 2.332 | -0.246 |
| 2b | 0.747 | 2.238 | -0.006 |
| 2c | 0.687 | 2.165 | 0.003 |
| 6 | 0.634 | 1.918 | -0.022 |
| BH | 0.934 | 2.128 | 0.142 |
| TA | 0.450 | 1.874 | -0.187 |

| comparison | difference | 95% CI | p |
|---|---:|---|---:|
| 2a - 1 | +0.320 | [-0.383, +1.014] | 0.360 |
| 2b - 1 | +0.373 | [-0.325, +1.039] | 0.287 |
| 2c - 1 | +0.313 | [-0.434, +1.068] | 0.401 |
| 6 - 1 | +0.260 | [-0.467, +0.986] | 0.476 |
| BH - 1 | +0.560 | [-0.083, +1.183] | 0.080 |
| TA - 1 | +0.076 | [-0.654, +0.796] | 0.837 |
