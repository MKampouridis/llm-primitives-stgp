# WP2 strategy generation report

Sessions: 28; accepted: 28; repaired: 0; resumed after interruption: 5.
Model ids seen: ['claude-opus-5-5']; Claude Code: ['2.1.316 (Claude Code)'].

| slot | accepted | backtests | checks | turns | minutes | output tokens | cache read | est. cost $ | dev-fit | dev-holdout |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s01_information_theory_1 | yes | 25 | 5 | 66 | 8 | 44,451 | 2,370,739 | 2.68 | 0.128 | 0.410 |
| s02_information_theory_2 | yes | 22 | 17 | 78 | 13 | 66,569 | 4,025,416 | 3.51 | 0.156 | 0.274 |
| s03_information_theory_3 | yes | 34 | 10 | 114 | 17 | 80,623 | 5,976,984 | 6.58 | 0.164 | -0.031 |
| s04_information_theory_4 | yes | 29 | 14 | 103 | 19 | 72,695 | 5,933,252 | 4.34 | 0.106 | 0.412 |
| s05_information_geometry_1 | yes | 23 | 3 | 65 | 8 | 45,087 | 2,491,046 | 2.67 | 0.014 | 0.492 |
| s06_information_geometry_2 | yes | 28 | 6 | 75 | 12 | 64,500 | 3,247,049 | 3.45 | -0.045 | -0.066 |
| s07_information_geometry_3 | yes | 20 | 9 | 78 | 12 | 58,186 | 2,253,325 | 3.90 | 0.184 | 0.525 |
| s08_information_geometry_4 | yes | 22 | 10 | 68 | 9 | 49,686 | 2,911,236 | 2.83 | 0.077 | 0.207 |
| s09_optimal_transport_1 | yes | 32 | 5 | 94 | 11 | 52,086 | 4,127,364 | 3.54 | 0.175 | 0.224 |
| s10_optimal_transport_2 | yes | 29 | 7 | 83 | 10 | 51,966 | 3,504,202 | 3.25 | 0.314 | 0.238 |
| s11_optimal_transport_3 | yes | 20 | 7 | 59 | 8 | 29,083 | 1,608,133 | 2.39 | 0.462 | 0.396 |
| s12_optimal_transport_4 | yes | 27 | 9 | 78 | 13 | 63,409 | 3,819,660 | 3.61 | 0.281 | 0.343 |
| s13_rough_paths_1 | yes | 22 | 10 | 65 | 12 | 45,712 | 2,599,136 | 2.68 | 0.169 | -0.008 |
| s14_rough_paths_2 | yes | 33 | 8 | 97 | 27 | 52,286 | 4,616,639 | 3.64 | -0.061 | 0.217 |
| s15_rough_paths_3 | yes | 25 | 6 | 77 | 12 | 63,657 | 3,245,702 | 3.44 | 0.090 | 0.427 |
| s16_rough_paths_4 | yes | 29 | 13 | 115 | 26 | 60,694 | 5,896,741 | 4.11 | 0.076 | 0.340 |
| s17_fractal_1 | yes | 29 | 9 | 80 | 9 | 46,850 | 3,700,948 | 3.17 | 0.245 | 0.366 |
| s18_fractal_2 | yes | 28 | 7 | 90 | 11 | 50,754 | 3,838,928 | 3.27 | 0.078 | 0.410 |
| s19_fractal_3 | yes | 33 | 9 | 100 | 11 | 57,767 | 4,614,503 | 3.79 | 0.261 | 0.769 |
| s20_fractal_4 | yes | 21 | 2 | 61 | 6 | 33,038 | 1,833,797 | 2.13 | 0.176 | 0.842 |
| s21_statistical_physics_1 | yes | 24 | 10 | 81 | 8 | 42,856 | 2,497,003 | 3.52 | -0.052 | 0.253 |
| s22_statistical_physics_2 | yes | 22 | 12 | 67 | 9 | 48,569 | 2,416,471 | 2.66 | 0.000 | 0.808 |
| s23_statistical_physics_3 | yes | 31 | 7 | 85 | 14 | 79,347 | 4,373,578 | 4.21 | 0.180 | 0.203 |
| s24_statistical_physics_4 | yes | 26 | 11 | 93 | 12 | 50,758 | 4,012,194 | 3.21 | 0.221 | 0.265 |
| s25_spectral_1 | yes | 26 | 15 | 88 | 28 | 42,790 | 4,103,935 | 3.09 | 0.278 | 0.759 |
| s26_spectral_2 | yes | 21 | 5 | 53 | 7 | 40,985 | 1,833,350 | 2.31 | 0.302 | 0.393 |
| s27_spectral_3 | yes | 22 | 10 | 68 | 8 | 47,892 | 2,636,819 | 2.70 | 0.084 | 0.604 |
| s28_spectral_4 | yes | 27 | 8 | 86 | 11 | 58,396 | 3,282,352 | 4.63 | -0.040 | 0.543 |

Totals: 352 minutes of session time, 1,500,692 output tokens, 97,770,502 cache-read tokens, estimated $95.32 at API prices (sessions ran on the PI's subscription; no API credit was used).
