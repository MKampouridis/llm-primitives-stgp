"""Two-scale signed p-variation imbalance (rough path theory).

The exact p-variation of the log-price path is computed by dynamic programming over all
partitions of the window. Along the optimal (variation-maximising) partition we record which
part of the p-variation is carried by up-legs and which by down-legs. The normalised difference
is a direction measure that is (i) invariant to volatility scale and (ii) determined by the
path's dominant oscillations at all scales rather than by its endpoints or by a fixed sampling
grid. A fast (30-bar) and a slow (252-bar) imbalance are added; the asset is held while the
sum is positive, and abandoned at once when the fast path turns into a coherent sell-off.
"""

from __future__ import annotations

import numpy as np

from strategy_api import LongWindow, PVar, Signal, Strategy, Window, trailing_windows


def _pvar_dp(rows: np.ndarray, p: float) -> tuple[np.ndarray, np.ndarray]:
    """Exact p-variation of each row path (vertices x_0..x_n) and the part of it carried by
    up-legs of the optimal partition.

    V(j) = max_{i<j} [ V(i) + |x_j - x_i|^p ],  V(0) = 0,  V_p = V(n)
    U(j) = U(i*) + 1{x_j > x_i*} |x_j - x_i*|^p   with i* the maximiser.
    (For p >= 1 the supremum over partitions of a piecewise-linear path is attained on vertices.)
    """
    T, m = rows.shape
    V = np.zeros((T, m))
    U = np.zeros((T, m))
    ar = np.arange(T)
    for j in range(1, m):
        inc = rows[:, j : j + 1] - rows[:, :j]
        cand = V[:, :j] + np.abs(inc) ** p
        k = np.argmax(cand, axis=1)
        V[:, j] = cand[ar, k]
        leg = inc[ar, k]
        U[:, j] = U[ar, k] + np.where(leg > 0, np.abs(leg) ** p, 0.0)
    return V[:, -1], U[:, -1]


def _imbalance(log_price: np.ndarray, window: int, p: float) -> np.ndarray:
    x = np.asarray(log_price, dtype=np.float64)
    rows = trailing_windows(x, window + 1)
    out = np.full(len(x), np.nan)
    ok = np.all(np.isfinite(rows), axis=1)
    if ok.any():
        V, U = _pvar_dp(rows[ok], p)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[ok] = np.where(V > 0, 2.0 * U / V - 1.0, 0.0)
    return out


def pvar_imbalance_fast(log_price, *, window, p):
    """Signed p-variation imbalance I = (U - D) / V_p in [-1, 1] over the last `window` bars."""
    return _imbalance(log_price, window, p)


def pvar_imbalance_slow(log_price, *, window, p):
    """Same functional over the last `window` (long) bars."""
    return _imbalance(log_price, window, p)


SIG_FAST = Signal(
    name="pvar_imbalance_fast",
    fn=pvar_imbalance_fast,
    inputs=("log_price",),
    params={"window": Window(30), "p": PVar(2.0)},
    lookback=lambda window, p: window + 1,
    description="signed p-variation imbalance of the log-price path, short window",
)

SIG_SLOW = Signal(
    name="pvar_imbalance_slow",
    fn=pvar_imbalance_slow,
    inputs=("log_price",),
    params={"window": LongWindow(252), "p": PVar(2.0)},
    lookback=lambda window, p: window + 1,
    description="signed p-variation imbalance of the log-price path, long window",
)

CRASH = -0.5  # fast imbalance below this = coherent sell-off dominates the recent path


def rule(s):
    a = s["pvar_imbalance_fast"]
    b = s["pvar_imbalance_slow"]
    ok = np.isfinite(a) & np.isfinite(b)
    score = a + b
    entry = np.where(ok, (score > 0.0).astype(float), np.nan)
    exit_ = np.where(ok, ((score < 0.0) | (a < CRASH)).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="two_scale_pvariation_imbalance",
    domain="rough_paths",
    hypothesis=(
        "The p-variation of a price path is a supremum over all partitions, so its optimal "
        "partition picks out the path's dominant oscillations (the legs that carry the "
        "roughness) independently of any fixed sampling grid or volatility level. Splitting "
        "the p-variation into the part carried by up-legs and by down-legs gives a scale-free "
        "measure of which direction dominates the path's rough structure. When the dominant "
        "legs are up at both a monthly and a yearly scale, the path is in a coherent advance "
        "and tends to continue (time-series momentum seen through the path's variation "
        "geometry); when the recent path is dominated by large down-legs (a coherent sell-off), "
        "subsequent risk-adjusted returns and drawdowns are poor. Holding only while the "
        "combined imbalance is positive, and leaving at once when the short-scale imbalance "
        "shows a coherent sell-off, should improve Sharpe and drawdown versus being always long, "
        "in any market with trending phases."
    ),
    definition=(
        "Let x_0..x_n be the log-price on the last n bars (piecewise-linear path X). For p >= 1, "
        "the p-variation is V_p(X) = sup over partitions 0 = t_0 < ... < t_k = n of "
        "sum_i |x_{t_i} - x_{t_{i-1}}|^p, attained on vertices and computed exactly by dynamic "
        "programming: V(0) = 0, V(j) = max_{i<j} [V(i) + |x_j - x_i|^p], V_p = V(n). Along the "
        "maximising partition pi* let U = sum over legs with x_{t_i} > x_{t_{i-1}} of "
        "|x_{t_i} - x_{t_{i-1}}|^p (up-leg variation) and D = V_p - U. The signed p-variation "
        "imbalance is I_n = (U - D) / V_p = 2U/V_p - 1, in [-1, 1]; it is invariant to scaling "
        "of the path, so needs no volatility normalisation. Signals: a_t = I over n = 30 bars, "
        "b_t = I over n = 252 bars, both with p = 2. Score s_t = a_t + b_t. Entry when s_t > 0; "
        "exit when s_t < 0 or a_t < -0.5 (the short-scale path is dominated by down-legs, a "
        "coherent sell-off). Long or flat only; the harness applies execution delay and costs."
    ),
    references=(
        "Lyons, T. J. (1998). Differential equations driven by rough signals. Revista Matematica "
        "Iberoamericana 14(2), 215-310.",
        "Friz, P. K. and Victoir, N. B. (2010). Multidimensional Stochastic Processes as Rough "
        "Paths: Theory and Applications. Cambridge University Press (ch. 5: p-variation).",
        "Friz, P. K. and Hairer, M. (2020). A Course on Rough Paths, 2nd ed. Springer.",
        "Butkus, V. and Norvaisa, R. (2018). Computation of p-variation. Lithuanian Mathematical "
        "Journal 58(4), 360-378.",
        "Cont, R. and Das, P. (2023). Quadratic variation and quadratic roughness. Bernoulli "
        "29(1), 496-522.",
        "Moskowitz, T. J., Ooi, Y. H. and Pedersen, L. H. (2012). Time series momentum. Journal "
        "of Financial Economics 104(2), 228-250.",
    ),
    signals=(SIG_FAST, SIG_SLOW),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Unlike the earlier price/quadratic-variation Levy-area rotation (a level-2 signature "
        "term of the 2-D path (X, [X]) on the fixed daily grid), this strategy uses the exact "
        "p-variation of the one-dimensional price path, a supremum over all partitions, and "
        "reads direction from the geometry of the optimal partition: which legs carry the "
        "path's variation. It needs no auxiliary coordinate and no volatility estimate. It is "
        "not a moving-average or return-sign rule: two paths with the same endpoint return can "
        "have opposite imbalance if one rises in a few large legs and the other in small steps "
        "broken by large drops. With p = 1 the same functional would collapse to the "
        "(conventional) efficiency ratio; p = 2 makes it a rough-path quantity that weights "
        "legs by their contribution to the path's 2-variation."
    ),
    limitations=(
        "Long-only: it earns little where there is no drift (most currency pairs scored slightly "
        "negative in development, around -0.15 to -0.3). It needs 253 bars of warm-up. The "
        "objective was quite sensitive to the short window (20/30/40 bars gave -0.15/-0.06/-0.17 "
        "in development), so the edge is modest and noisy. On slow-moving markets the trade "
        "count can come close to the 2-entries-per-year minimum. The exact dynamic programme "
        "costs O(n^2) per bar (fine at n = 252 on daily data). Sharp gap-downs are only caught "
        "after the close at which they happen."
    ),
)
