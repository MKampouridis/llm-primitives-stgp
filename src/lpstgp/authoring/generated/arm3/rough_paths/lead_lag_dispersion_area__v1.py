"""lead_lag_dispersion_area: Levy area between a return stream and its own dispersion stream."""

from __future__ import annotations

import numpy as np

from operator_api import LongWindow, Operator, Real, Series, trailing_windows


def _impl(series: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(series, dtype=np.float64)
    n = int(window)
    T = len(x)
    out = np.full(T, np.nan)
    if T < n:
        return out
    W = trailing_windows(x, n)[n - 1 :]          # rows: x_{t-n+1} .. x_t
    a = W - W.mean(axis=1, keepdims=True)        # price innovations
    d = np.abs(a)
    b = d - d.mean(axis=1, keepdims=True)        # dispersion innovations
    A = np.cumsum(a, axis=1)
    B = np.cumsum(b, axis=1)
    # Levy area of the piecewise-linear path (A, B):  1/2 sum_j (A_{j-1} b_j - B_{j-1} a_j)
    area = 0.5 * np.sum(A[:, :-1] * b[:, 1:] - B[:, :-1] * a[:, 1:], axis=1)
    sa = np.sqrt(np.mean(a * a, axis=1))
    sb = np.sqrt(np.mean(b * b, axis=1))
    norm = n * sa * sb
    with np.errstate(invalid="ignore", divide="ignore"):
        val = area / norm
    val[~(norm > 0)] = np.nan
    val[~np.isfinite(val)] = np.nan
    out[n - 1 :] = val
    return out


OPERATOR = Operator(
    name="lead_lag_dispersion_area",
    summary=(
        "Normalised Levy area of the planar path formed by the cumulative (demeaned) returns "
        "and the cumulative (demeaned) absolute deviations: which of price and volatility "
        "leads the other. Negative = falls precede volatility bursts or bursts precede "
        "rebounds (leverage / fear); positive = rises precede volatility or volatility "
        "precedes falls."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="propagate",
    definition=(
        "On the last n = window values x_1..x_n form a_i = x_i - mean(x) and "
        "b_i = |a_i| - mean(|a|), and the two-dimensional stream with cumulative coordinates "
        "A_j = sum_{i<=j} a_i (price) and B_j = sum_{i<=j} b_i (excess dispersion clock). "
        "The level-2 signature of its piecewise-linear interpolation has antisymmetric part "
        "(Levy area) L = 1/2 int (A dB - B dA) = 1/2 sum_j (A_{j-1} b_j - B_{j-1} a_j) "
        "= 1/2 sum_{i<j} (a_i b_j - b_i a_j), i.e. n/2 times the sum over all positive lags "
        "of the antisymmetrised cross-covariance c_ab(k) - c_ba(k). The area is the standard "
        "signature statistic for lead-lag between two streams: it is zero when neither leads "
        "and its sign tells which one moves first. Output: L / (n * rms(a) * rms(b)), "
        "invariant to rescaling the input, O(1) under independence."
    ),
    references=(
        "Gyurko, L. G., Lyons, T., Kontkowski, M., Field, J. (2013). Extracting information "
        "from the signature of a financial data stream. arXiv:1307.7244.",
        "Flint, G., Hambly, B., Lyons, T. (2016). Discretely sampled signals and the rough Hoff "
        "process. Stochastic Processes and their Applications 126(9), 2593-2614.",
        "Chevyrev, I., Kormilitzin, A. (2016). A primer on the signature method in machine learning. "
        "arXiv:1603.03788.",
        "Black, F. (1976). Studies of stock price volatility changes. Proceedings of the "
        "American Statistical Association, Business and Economic Statistics Section, 177-181.",
    ),
    impl=_impl,
    invariances=("scale",),
)
