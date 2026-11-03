"""variance_clock_transport: Wasserstein-1 distance between the realised-variance clock and the
calendar clock over a trailing window."""

import numpy as np

from operator_api import LongWindow, Operator, Real, Series, trailing_windows


def _impl(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    w = int(window)
    out = np.full(len(x), np.nan)
    if len(x) < w:
        return out
    X = trailing_windows(x, w)[w - 1 :]
    valid = np.all(np.isfinite(X), axis=1)
    q = np.where(valid[:, None], X, 0.0) ** 2
    tot = q.sum(axis=1)
    F = np.cumsum(q, axis=1)[:, :-1]  # variance-clock CDF at k = 1..w-1
    G = np.arange(1, w, dtype=np.float64) / w  # calendar-clock CDF
    with np.errstate(invalid="ignore", divide="ignore"):
        Fn = F / tot[:, None]
        w1 = np.abs(Fn - G[None, :]).sum(axis=1) / w
    w1max = (w - 1) / (2.0 * w)  # all variance on one end bar
    val = np.where(tot > 0.0, w1 / w1max, 0.0)
    val[~valid] = np.nan
    out[w - 1 :] = val
    return out


OPERATOR = Operator(
    name="variance_clock_transport",
    summary=(
        "Normalised Wasserstein-1 distance between the realised-variance (business-time) clock "
        "and the calendar clock over the window: 0 = variance spread evenly in time, 1 = all of "
        "it in a single end bar; high values mark bursts, clusters or trends of volatility."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="propagate",
    definition=(
        "Over the last w bars s = 1..w define the variance-clock measure "
        "mu = sum_s m_s delta_{s/w} with m_s = x_s^2 / sum_r x_r^2 (the quadratic-variation "
        "time change of Dambis-Dubins-Schwarz / Clark subordination) and the calendar measure "
        "lambda = (1/w) sum_s delta_{s/w}. On the line W1(mu, lambda) = int |F_mu - F_lambda|, "
        "here (1/w) sum_{k=1}^{w-1} |sum_{s<=k} m_s - k/w|. Its maximum over probability "
        "vectors, (w-1)/(2w), is attained when all mass sits on the first or the last bar, so "
        "the output is V = W1(mu, lambda) / ((w-1)/(2w)) in [0, 1] (0 for an all-zero window). "
        "V is the earth mover's cost of re-timing calendar time into business time; it is "
        "invariant to rescaling x."
    ),
    references=(
        "Villani, C. (2003). Topics in Optimal Transportation. AMS, Graduate Studies in "
        "Mathematics 58 (Thm 2.18: W1 on the line as the L1 distance of distribution functions).",
        "Vallender, S. S. (1974). Calculation of the Wasserstein distance between probability "
        "distributions on the line. Theory of Probability and Its Applications 18(4), 784-786.",
        "Ane, T. and Geman, H. (2000). Order flow, transaction clock, and normality of asset "
        "returns. Journal of Finance 55(5), 2259-2284.",
    ),
    impl=_impl,
    invariances=("scale",),
)
