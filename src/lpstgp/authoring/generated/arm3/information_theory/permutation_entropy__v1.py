"""Normalised permutation entropy (Bandt-Pompe) of a series over a trailing window."""

import math

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

_ORDER = 3
_N_PATTERNS = math.factorial(_ORDER)  # 6
_MIN_VALID = 0.8


def _pattern_codes(x: np.ndarray) -> np.ndarray:
    """Ordinal pattern of (x[i-2], x[i-1], x[i]) coded 0..5 (ties: 'greater' is false);
    -1 where the triple is incomplete."""
    T = len(x)
    codes = np.full(T, -1, dtype=np.int64)
    if T < _ORDER:
        return codes
    a, b, c = x[:-2], x[1:-1], x[2:]
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(c)
    raw = (a > b).astype(np.int64) * 4 + (b > c).astype(np.int64) * 2 + (a > c).astype(np.int64)
    # raw takes only the six values {0, 2, 3, 4, 5, 7} (1 and 6 are inconsistent); map to 0..5
    lut = np.full(8, -1, dtype=np.int64)
    lut[[0, 2, 3, 4, 5, 7]] = np.arange(6)
    codes[2:] = np.where(ok, lut[raw], -1)
    return codes


def _impl(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    n_pat = window - _ORDER + 1  # patterns whose three values all lie inside the window
    if T < window:
        return out
    codes = _pattern_codes(x)
    onehot = np.zeros((T + 1, _N_PATTERNS))
    valid = codes >= 0
    onehot[1:][valid, codes[valid]] = 1.0
    cum = np.cumsum(onehot, axis=0)
    t = np.arange(window - 1, T)
    counts = cum[t + 1] - cum[t + 1 - n_pat]  # patterns ending at t-n_pat+1 .. t
    n = counts.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = counts / n[:, None]
        h = -np.nansum(np.where(p > 0, p * np.log(p), 0.0), axis=1) / math.log(_N_PATTERNS)
    h[n < _MIN_VALID * n_pat] = np.nan
    out[t] = h
    return out


OPERATOR = Operator(
    name="permutation_entropy",
    summary=(
        "Normalised Shannon entropy of order-3 ordinal patterns of the series over a trailing "
        "window: 1 = all up/down orderings equally likely, lower = predictable ordinal structure."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="min_valid",
    min_valid=_MIN_VALID,
    definition=(
        "For each i let pi_i be the ordinal pattern (permutation that sorts) of the triple "
        "(x_{i-2}, x_{i-1}, x_i), one of 3! = 6 patterns (ties are resolved by treating equal "
        "values as not greater). Over the window [t-w+1, t] take the w-2 triples lying fully "
        "inside it, drop any with a missing value, and form the relative frequencies p_k of "
        "the six patterns. The output is the normalised permutation entropy "
        "H_t = -sum_k p_k ln p_k / ln 6, in [0, 1]. NaN if fewer than 80% of the w-2 triples "
        "are complete. Ordinal patterns depend only on order relations, so the feature is "
        "invariant to positive rescaling (indeed to any increasing transform) of the input."
    ),
    references=(
        "Bandt, C. and Pompe, B. (2002). Permutation entropy: a natural complexity measure for "
        "time series. Physical Review Letters 88(17), 174102.",
        "Zanin, M., Zunino, L., Rosso, O. A. and Papo, D. (2012). Permutation entropy and its "
        "main biomedical and econophysics applications: a review. Entropy 14(8), 1553-1577.",
        "Zunino, L., Zanin, M., Tabak, B. M., Perez, D. G. and Rosso, O. A. (2009). Forbidden "
        "patterns, permutation entropy and stock market inefficiency. Physica A 388(14), "
        "2854-2864.",
    ),
    impl=_impl,
    invariances=("scale",),
)
