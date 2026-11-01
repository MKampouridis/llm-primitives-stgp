"""Price / quadratic-variation Levy-area rotation (rough path theory).

Over a trailing window the strategy builds the two-dimensional path Z = (X, V) where X is the
normalised log-price and V the centred, normalised cumulative quadratic variation (the
"variance clock").  The level-2 signature of Z contains one non-trivial antisymmetric term, the
Levy area A(X, V), which measures the signed area swept by the path in the price/variance plane,
i.e. the order in which price moves and variance arrive.  The strategy is long while that rotation
is non-negative and steps out when it turns clearly negative.
"""
from __future__ import annotations

import numpy as np

from strategy_api import Signal, Strategy, Window, trailing_windows


def price_qv_levy_area(log_return, *, window):
    """Unit-scaled Levy area of the piecewise-linear path (X, V) over the last `window` bars.

    dX_i = r_i / sqrt(sum r^2)                    (unit total quadratic variation)
    dV_i = (r_i^2 - mean r^2) / ||r^2 - mean r^2|| (centred QV increments, V is a bridge 0 -> 0)
    A    = 1/2 * sum_i (X_{i-1} dV_i - V_{i-1} dX_i)   (exact area of the piecewise-linear path)
    returned value = A / 0.5  (0.5 = scale of the area of two unit Brownian channels)
    """
    r = np.asarray(log_return, dtype=np.float64)
    rows = trailing_windows(r, window)
    dx = rows / (np.sqrt(np.sum(rows ** 2, axis=1, keepdims=True)) + 1e-18)
    e = rows ** 2
    dv = e - np.mean(e, axis=1, keepdims=True)
    dv = dv / (np.sqrt(np.sum(dv ** 2, axis=1, keepdims=True)) + 1e-18)
    x = np.cumsum(dx, axis=1) - dx  # left-point values X_{i-1}
    v = np.cumsum(dv, axis=1) - dv  # left-point values V_{i-1}
    area = 0.5 * np.sum(x * dv - v * dx, axis=1)
    return area / 0.5


AREA = Signal(
    name="price_qv_levy_area",
    fn=price_qv_levy_area,
    inputs=("log_return",),
    params={"window": Window(40)},
    lookback=lambda window: window,
    description="Levy area between normalised log-price and centred quadratic-variation clock",
)

ENTRY_LEVEL = 0.0   # enter when the price/QV rotation is non-negative
EXIT_LEVEL = -0.5   # leave when it is clearly negative (hysteresis band of half a unit)


def rule(signals):
    a = signals["price_qv_levy_area"]
    ok = np.isfinite(a)
    entry = np.where(ok, (a > ENTRY_LEVEL).astype(float), np.nan)
    exit_ = np.where(ok, (a < EXIT_LEVEL).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="price_qv_levy_area_rotation",
    domain="rough_paths",
    hypothesis=(
        "The joint path of price and its own quadratic variation carries information that neither "
        "coordinate carries alone: the order in which returns and variance arrive. This order is "
        "captured exactly by the Levy area of the 2-D path (X, [X]), the antisymmetric part of its "
        "level-2 signature. A strongly negative area marks a price/variance rotation typical of "
        "stress (variance building up while the price falls, positively skewed moves being given "
        "back, a leverage-effect regime), which tends to come before poor risk-adjusted returns and "
        "deep drawdowns. A non-negative area marks benign rotation. Holding the asset only while "
        "the rotation is not clearly negative should improve Sharpe and drawdown versus being "
        "always long, in any market where volatility and returns interact."
    ),
    definition=(
        "For each bar t take the last W=40 daily log returns r_1..r_W (bars t-W+1..t). "
        "Price channel: dX_i = r_i / sqrt(sum_j r_j^2), so X has unit quadratic variation over "
        "the window. Variance channel (centred quadratic-variation clock): "
        "dV_i = (r_i^2 - m) / sqrt(sum_j (r_j^2 - m)^2), with m = mean_j r_j^2, so V is a bridge "
        "from 0 to 0 with unit length scale. With X_0 = V_0 = 0 and the cumulative sums X_i, V_i, "
        "the signature Levy area of the piecewise-linear path Z = (X, V) is "
        "A_t = 1/2 * (S^{XV} - S^{VX}) = 1/2 * sum_i (X_{i-1} dV_i - V_{i-1} dX_i), "
        "which is exact for piecewise-linear paths (shoelace formula). Equivalently, by summation by "
        "parts, A_t = -sum_i V_{i-1} dX_i - 1/2 sum_i dX_i dV_i: a variance-clock-weighted return "
        "plus a cross-variation (co-skewness) term. The signal is s_t = A_t / 0.5, which is of order "
        "one for two independent unit Brownian channels. Rule: entry condition s_t > 0; exit "
        "condition s_t < -0.5 (hysteresis band). The harness holds the long from entry to exit."
    ),
    references=(
        "Lyons, T. (1998). Differential equations driven by rough signals. Revista Matematica "
        "Iberoamericana 14(2), 215-310.",
        "Levy, P. (1940). Le mouvement brownien plan. American Journal of Mathematics 62(1), "
        "487-550.",
        "Friz, P. K. & Victoir, N. B. (2010). Multidimensional Stochastic Processes as Rough Paths. "
        "Cambridge University Press.",
        "Gyurko, L. G., Lyons, T., Kontkowski, M. & Field, J. (2013). Extracting information from "
        "the signature of a financial data stream. arXiv:1307.7244.",
        "Chevyrev, I. & Kormilitzin, A. (2016). A primer on the signature method in machine "
        "learning. arXiv:1603.03788.",
        "Flint, G., Hambly, B. & Lyons, T. (2016). Discretely sampled signals and the rough Hoff "
        "process. Stochastic Processes and their Applications 126(9), 2593-2614.",
        "Black, F. (1976). Studies of stock price volatility changes. Proceedings of the 1976 "
        "Meetings of the American Statistical Association, Business and Economic Statistics "
        "Section, 177-181.",
    ),
    signals=(AREA,),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Uses one signature term, the Levy area between a price path and its own (centred) "
        "quadratic-variation clock, as a stand-alone regime signal. It is not a trend, "
        "volatility-level or skewness indicator: both channels are scale-normalised within the "
        "window, so the signal ignores the level of volatility and depends only on the "
        "geometric order (rotation) of price and variance increments. Normalising each channel "
        "to unit length makes the thresholds comparable across asset classes and volatility "
        "regimes without fitting per instrument."
    ),
    limitations=(
        "The predictive content is weak and noisy: development results changed noticeably with "
        "the window (20/40/60) and the exit band. Longer windows or wider bands can fall below the "
        "minimum trade frequency, and W=40 with a -0.5 band leaves only about a 1.5-2x margin "
        "above it. The signal is "
        "symmetric across assets, so markets with no drift (some currency pairs) are held about "
        "half the time with roughly zero expected return; it gave persistent losses on a few FX "
        "pairs and one equity index. Squared returns make V sensitive to single extreme days. "
        "Binary positions only, with no volatility sizing. The thresholds (0, -0.5) were chosen on "
        "the development data."
    ),
)
