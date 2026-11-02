# WP2 budget unit and fitness weights (protocol §6.2-6.3)

Every GP arm at the chosen parameters, 3 runs on SPX, NKY, EURUSD, USDJPY, GOLD, NATGAS (PL1).

| arm (library) | median unique share | ms per requested evaluation (median) |
|---|---:|---:|
| s2a | 0.130 | 0.65 |
| s2b | 0.147 | 0.97 |
| s2c | 0.143 | 4.59 |
| seed | 0.152 | 3.51 |
| technical | 0.120 | 0.92 |

Spread of unique shares: 1.26x -> budget unit **requested** (rule: unique if > 2x).

| lambda_turnover | runs | final rules with no trade | median validation turnover |
|---:|---|---:|---:|
| x1 | step 2 | 0.0% | 11.9 |

Rule: no-trade share <= 25% and median turnover <= 50 a year -> **lambda_turnover x1**.
For reference, the step-1 runs (all candidates, arms 2c and 6): no trade 0.6%, median turnover 11.1 (D-051).
