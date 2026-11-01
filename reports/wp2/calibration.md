# WP2 calibration: GP parameters at equal budget (protocol §6.1)

Arms 2c and 6 pooled; SPX, NKY, EURUSD, USDJPY, GOLD, NATGAS; PL1 training data only; 10 runs per arm and instrument; 50,000 requested evaluations per candidate.

| population | tournament | runs | median validation F | median convergence gen | generations | evaluations |
|---:|---:|---:|---:|---:|---:|---:|
| 250 | 3 | 120 | 0.5889 | 58 | 60 | 15,250 |
| 250 | 5 | 120 | 0.6738 | 64 | 70 | 17,750 |
| 500 | 3 | 120 | 0.6025 | 41 | 50 | 25,500 |
| 500 | 5 | 120 | 0.4948 | 36 | 40 | 20,500 |
| 1000 | 3 | 120 | 0.3763 | 32 | 40 | 41,000 |
| 1000 | 5 | 120 | 0.6469 | 27 | 30 | 31,000 |

**Chosen:** population 250, tournament 5, 70 generations (17,750 requested evaluations): the cheapest candidate within 0.05 of the best median validation F (0.6738).
