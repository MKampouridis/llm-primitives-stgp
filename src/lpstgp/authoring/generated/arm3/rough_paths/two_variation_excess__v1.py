"""two_variation_excess: log ratio of the 2-variation of the path to its quadratic variation."""

from __future__ import annotations

import numpy as np

from operator_api import LongWindow, Operator, Path, Real, trailing_windows


def _impl(path: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(path, dtype=np.float64)
    n = int(window)
    T = len(x)
    out = np.full(T, np.nan)
    if T < n + 1:
        return out
    W = trailing_windows(x, n + 1)[n:]
    W = W - W[:, :1]
    M = W.shape[0]
    # Dynamic programme over partitions 0 = k_0 < ... < k_m = n:
    #   V_j = max_{i<j} V_i + (W_j - W_i)^2,  V_0 = 0;  2-variation = V_n.
    V = np.zeros((M, n + 1))
    for j in range(1, n + 1):
        d = W[:, j : j + 1] - W[:, :j]
        V[:, j] = np.max(V[:, :j] + d * d, axis=1)
    dW = np.diff(W, axis=1)
    qv = np.sum(dW * dW, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        val = np.log(V[:, n] / qv)
    val[~(qv > 0)] = np.nan
    val[~np.isfinite(val)] = np.nan
    out[n:] = val
    return out


OPERATOR = Operator(
    name="two_variation_excess",
    summary=(
        "Log of the ratio between the 2-variation of the path over the window (supremum over "
        "all partitions of the sum of squared increments) and its quadratic variation on the "
        "daily grid: near 0 = choppy, mean-reverting path whose oscillations cancel; large = "
        "persistent excursions that coarse partitions capture far better than daily ones."
    ),
    inputs=(Path,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window) + 1,
    missing="propagate",
    definition=(
        "For the path values X_{t-n}, ..., X_t (n = window) the p-variation with p = 2 is "
        "||X||_{2-var}^2 = sup over partitions t-n = k_0 < k_1 < ... < k_m = t of "
        "sum_i |X_{k_i} - X_{k_{i-1}}|^2, computed exactly by the dynamic programme "
        "V_j = max_{i<j} (V_i + (X_j - X_i)^2), V_0 = 0. p = 2 is the critical exponent of "
        "rough path theory (Young integration below it, the Levy-area lift above it); the "
        "finest partition gives the realised quadratic variation QV = sum (dX)^2 <= V_n. "
        "Output: log(V_n / QV) >= 0. It is 0 when every coarsening loses variation (strictly "
        "alternating increments), grows slowly (log log n) for a random walk, and grows like "
        "log(n mu^2 / sigma^2) for a trend; it is invariant to shifting and rescaling the path."
    ),
    references=(
        "Lyons, T. J. (1998). Differential equations driven by rough signals. Revista "
        "Matematica Iberoamericana 14(2), 215-310.",
        "Friz, P. K., Victoir, N. B. (2010). Multidimensional Stochastic Processes as Rough "
        "Paths: Theory and Applications. Cambridge University Press (ch. 5, p-variation).",
        "Butkus, V., Norvaisa, R. (2018). Computation of p-variation. Lithuanian Mathematical "
        "Journal 58(4), 360-378.",
        "Taylor, S. J. (1972). Exact asymptotic estimates of Brownian path variation. Duke "
        "Mathematical Journal 39(2), 219-241.",
    ),
    impl=_impl,
    invariances=("shift", "scale"),
)
