"""Bias-corrected lagged mutual information of a series with itself (tercile coding)."""

import math

import numpy as np

from operator_api import Lag, LongWindow, Operator, Real, Series

_K = 3  # symbols (empirical terciles)
_MIN_VALID = 0.8


def _impl(x: np.ndarray, window: int, lag: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    n_pairs = window - lag
    norm = math.log(_K)
    for t in range(window - 1, T):
        w = x[t - window + 1 : t + 1]
        fin = np.isfinite(w)
        v = w[fin]
        if len(v) < _MIN_VALID * window:
            continue
        # tercile thresholds taken as actual data values (exactly scale-equivariant)
        q1, q2 = np.quantile(v, [1.0 / 3.0, 2.0 / 3.0], method="lower")
        s = (w > q1).astype(np.int64) + (w > q2).astype(np.int64)
        a, b = s[:-lag], s[lag:]
        ok = fin[:-lag] & fin[lag:]
        n = int(ok.sum())
        if n < _MIN_VALID * n_pairs or n < 2:
            continue
        joint = np.bincount(a[ok] * _K + b[ok], minlength=_K * _K).reshape(_K, _K) / n
        pa = joint.sum(axis=1)
        pb = joint.sum(axis=0)
        nz = joint > 0
        mi = float(np.sum(joint[nz] * np.log(joint[nz] / np.outer(pa, pb)[nz])))
        # Miller-Madow bias correction for the plug-in MI estimate
        ka = int((pa > 0).sum())
        kb = int((pb > 0).sum())
        mi -= (ka - 1) * (kb - 1) / (2.0 * n)
        out[t] = mi / norm
    return out


OPERATOR = Operator(
    name="lagged_mutual_information",
    summary=(
        "Bias-corrected mutual information between the series and its own value `lag` bars "
        "earlier, both coded into window terciles: how much (linear or nonlinear) information "
        "the past carries about the present."
    ),
    inputs=(Series,),
    params=(("window", LongWindow), ("lag", Lag)),
    output=Real,
    lookback=lambda window, lag: int(window),
    missing="min_valid",
    min_valid=_MIN_VALID,
    definition=(
        "In the window [t-w+1, t] code each valid x_i into a symbol s_i in {0, 1, 2} by the "
        "empirical terciles of the window's valid values (lower-type quantiles, so thresholds "
        "are data values). Over the w - lag pairs (s_{i-lag}, s_i) lying inside the window and "
        "both valid (n pairs) form the joint frequencies p_ab and marginals p_a, p_b. The "
        "plug-in mutual information I = sum_ab p_ab ln(p_ab / (p_a p_b)) is corrected for its "
        "positive finite-sample bias with the Miller-Madow first-order term under independence, "
        "I_MM = I - (K_a - 1)(K_b - 1) / (2n) with K_a, K_b the numbers of occupied symbols, "
        "and normalised by ln 3 (the maximum), so "
        "independence gives values near 0 (possibly slightly negative) and perfect "
        "predictability gives 1. Applied to ret it captures serial dependence of signed moves "
        "including volatility clustering (extreme terciles following each other); applied to "
        "abs_ret it measures volatility persistence. Rank coding makes it scale-invariant. "
        "NaN if fewer than 80% of values or pairs are valid."
    ),
    references=(
        "Shannon, C. E. (1948). A mathematical theory of communication. Bell System Technical "
        "Journal 27, 379-423 and 623-656.",
        "Fraser, A. M. and Swinney, H. L. (1986). Independent coordinates for strange attractors "
        "from mutual information. Physical Review A 33(2), 1134-1140.",
        "Darbellay, G. A. and Wuertz, D. (2000). The entropy as a tool for analysing statistical "
        "dependences in financial time series. Physica A 287(3-4), 429-439.",
        "Paninski, L. (2003). Estimation of entropy and mutual information. Neural Computation "
        "15(6), 1191-1253.",
    ),
    impl=_impl,
    invariances=("scale",),
)
