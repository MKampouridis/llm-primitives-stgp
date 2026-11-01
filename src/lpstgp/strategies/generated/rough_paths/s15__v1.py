"""multiscale_time_price_levy_area_pullback

Rough-path strategy built on the level-2 signature of the *time-augmented* log-price path
(t, X): its Levy area, normalised by the Levy area of the lead-lag path (= half the quadratic
variation), averaged over three nested time scales. A concave path (negative area: the
increments were front-loaded and the path now sits above its chord) is bought; the position is
closed as soon as the path's signed area returns to non-negative (the late part of the window has
caught up with the early part).
"""

from __future__ import annotations

import numpy as np

from strategy_api import Signal, Strategy, Window, trailing_windows

SCALES = (1, 2, 3)  # window multiples: W, 2W, 3W
ENTRY_AREA = -0.2  # enter when the scale-averaged normalised area is below this (concave path)
EXIT_AREA = 0.0  # leave when it is above this (concavity resolved)


def _normalised_time_price_area(r: np.ndarray, window: int) -> np.ndarray:
    """A(t,X) / sqrt(QV) on the trailing `window` bars, for every bar (NaN until available).

    For the piecewise-linear interpolation of (u_k, x_k), u_k = k/W, x_k = sum_{j<=k} r_j, the
    Levy area of the 2-D path is exactly  A = 1/2 (S^{u,x} - S^{x,u}) = sum_k (u_{k-1/2} - 1/2) r_k,
    with u_{k-1/2} = (k - 1/2)/W the midpoint of segment k. QV = sum_k r_k^2 is twice the Levy area
    of the lead-lag transform of x, so the ratio is a dimensionless signature statistic.
    """
    rows = trailing_windows(r, window)
    ok = np.all(np.isfinite(rows), axis=1)
    dx = np.where(ok[:, None], rows, 0.0)
    u_mid = (np.arange(window) + 0.5) / window
    area = np.sum((u_mid - 0.5)[None, :] * dx, axis=1)
    qv = np.sum(dx * dx, axis=1)
    good = ok & (qv > 0)
    return np.where(good, area / np.sqrt(np.where(qv > 0, qv, 1.0)), np.nan)


def time_price_area(log_return, *, window):
    r = np.asarray(log_return, dtype=np.float64)
    parts = np.vstack([_normalised_time_price_area(r, window * m) for m in SCALES])
    return np.mean(parts, axis=0)  # NaN until the longest scale is available


SIGNALS = (
    Signal(
        name="time_price_area",
        fn=time_price_area,
        inputs=("log_return",),
        params={"window": Window(20)},
        lookback=lambda window: int(max(SCALES) * window),
        description=(
            "Levy area of the time-augmented log-price path (level-2 signature, antisymmetric "
            "part) divided by sqrt(quadratic variation), averaged over windows W, 2W, 3W."
        ),
    ),
)


def rule(signals):
    a = signals["time_price_area"]
    fin = np.isfinite(a)
    entry = np.where(fin, (a < ENTRY_AREA).astype(float), np.nan)
    exit_ = np.where(fin, (a > EXIT_AREA).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="multiscale_time_price_levy_area_pullback",
    domain="rough_paths",
    hypothesis=(
        "The order in which a price path's increments arrive in time is encoded exactly by the "
        "Levy area of the time-augmented path (t, X), the antisymmetric part of its level-2 "
        "signature; it is zero for a straight line, negative when the path lies above its chord "
        "(gains front-loaded, recent relative weakness: a concave path / pullback) and positive "
        "when it lies below it (convex, late acceleration). Scaled by sqrt of the lead-lag area "
        "(quadratic variation) it is a dimensionless, volatility-free shape statistic. "
        "Short-horizon return shapes in liquid markets tend to partially revert, so a clearly "
        "concave path at the 1-3 month scales marks a temporary dislocation whose correction "
        "earns the asset's drift plus a reversal premium; once the signed area has returned to "
        "non-negative the dislocation is used up. Holding only through these concave episodes "
        "(about a quarter to a third of the time) should improve risk-adjusted return per unit "
        "of drawdown versus being always long, in any market with positive drift and "
        "short-horizon mean reversion."
    ),
    definition=(
        "Let r_k be daily log returns and, for a window of W bars ending at t, x_k = sum_{j<=k} "
        "r_{t-W+j}, u_k = k/W (k = 0..W). The time-augmented path is the piecewise-linear "
        "interpolation of (u_k, x_k). Its level-2 signature S^{ij} = int dZ^i dZ^j gives the Levy "
        "area A_W(t) = 1/2 (S^{u x} - S^{x u}) = int_0^1 (u - 1/2) dx = sum_{k=1}^{W} "
        "((k - 1/2)/W - 1/2) r_{t-W+k} (exact for the PL path). Its normaliser is the lead-lag "
        "Levy area L_W(t) = 1/2 sum_k r_{t-W+k}^2 = QV_W/2. The signal is "
        "s(t) = (1/3) sum_{m=1}^{3} A_{mW}(t) / sqrt(QV_{mW}(t)), W = 20 (scales 20, 40, 60 bars); "
        "under a driftless random walk each term has mean 0 and standard deviation about "
        "sqrt(1/12) = 0.29. Rule: entry when s(t) < -0.2 (path clearly concave/above its chord), "
        "exit when s(t) > 0 (signed area restored); the harness holds the long position between "
        "entry and exit. Lookback 60 bars."
    ),
    references=(
        "Lyons, T. (1998). Differential equations driven by rough signals. Revista Matematica "
        "Iberoamericana 14(2), 215-310.",
        "Chevyrev, I. and Kormilitzin, A. (2016). A primer on the signature method in machine "
        "learning. arXiv:1603.03788.",
        "Levin, D., Lyons, T. and Ni, H. (2013). Learning from the past, predicting the statistics "
        "for the future, learning an evolving system. arXiv:1309.0260.",
        "Flint, G., Hambly, B. and Lyons, T. (2016). Discretely sampled signals and the rough Hoff "
        "process. Stochastic Processes and their Applications 126(9), 2593-2614.",
        "Levy, P. (1940). Le mouvement brownien plan. American Journal of Mathematics 62(1), "
        "487-550.",
        "Jegadeesh, N. (1990). Evidence of predictable behavior of security returns. Journal of "
        "Finance 45(3), 881-898.",
    ),
    signals=SIGNALS,
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Earlier strategies in this family used the Levy area of (price, quadratic variation) and "
        "a p-variation up/down imbalance. This one uses a different object: the Levy area of the "
        "time-augmented path (t, X), i.e. the time-ordering of increments relative to the chord, "
        "made scale-free by dividing by sqrt of the lead-lag Levy area, and averaged over nested "
        "scales. It needs no volatility path, no partition optimisation, and trades concavity "
        "(pullbacks) rather than direction or variance rotation."
    ),
    limitations=(
        "For a one-dimensional price the time-price Levy area is linear in the returns (a "
        "time-weighted contrast of late versus early returns), so the signal is close to a "
        "short-horizon reversal filter; its novelty is the signature-based, volatility-free "
        "normalisation and multiscale shape reading rather than access to nonlinear information. "
        "On the development data the edge was weak and noisy: the mirror rule (buying convex "
        "paths) scored comparably on some variants, neighbouring thresholds and scales scored "
        "between -0.03 and +0.09, and per-instrument results moved a lot under small changes. "
        "Driftless markets (most FX pairs) score negative because any long exposure there pays "
        "drawdown without return. It buys into declines (a concave path includes accelerating "
        "sell-offs), so in persistent bear markets or strongly trending assets (some "
        "cryptocurrencies, bonds in rate-trend regimes) it can catch falling prices. Exposure is "
        "roughly 25-35% with about 6-8 round trips per year."
    ),
)
