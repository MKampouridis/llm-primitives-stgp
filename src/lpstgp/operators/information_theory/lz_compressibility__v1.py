"""LZCompressibility: normalised Lempel-Ziv (1976) complexity of the quantised window.

Quantising to fewer levels is a coarser (higher-distortion) description of the series, so the
normalised complexity at a given number of levels is an entropy-rate proxy at that distortion.
"""

import numpy as np
from numba import njit

from lpstgp.operators._kernels import min_count, quantile_sorted, window_values
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import Levels, Real, Series, Window

MIN_VALID = 0.9


@njit(cache=True)
def lz76(s: np.ndarray) -> int:
    """Number of phrases in the Lempel-Ziv (1976) parsing (Kaspar & Schuster 1987 algorithm)."""
    n = len(s)
    if n < 2:
        return n
    i, k, ell = 0, 1, 1
    c, k_max = 1, 1
    while True:
        if s[i + k - 1] == s[ell + k - 1]:
            k += 1
            if ell + k > n:
                c += 1
                break
        else:
            if k > k_max:
                k_max = k
            i += 1
            if i == ell:
                c += 1
                ell += k_max
                if ell + 1 > n:
                    break
                i = 0
                k = 1
                k_max = 1
            else:
                k = 1
    return c


@njit(cache=True)
def _lz_rolling(x: np.ndarray, window: int, levels: int, min_valid: float) -> np.ndarray:
    n = len(x)
    out = np.full(n, np.nan)
    need = max(min_count(window, min_valid), 4)
    thresholds = np.empty(levels - 1)
    for t in range(window - 1, n):
        vals = window_values(x, t, window)
        m = len(vals)
        if m < need:
            continue
        ordered = np.sort(vals)
        for k in range(1, levels):
            thresholds[k - 1] = quantile_sorted(ordered, k / levels)
        symbols = np.empty(m, dtype=np.int64)
        seen = np.zeros(levels, dtype=np.bool_)
        for j in range(m):
            sym = int(np.searchsorted(thresholds, vals[j], side="right"))
            symbols[j] = sym
            seen[sym] = True
        distinct = 0
        for k in range(levels):
            distinct += seen[k]
        if distinct < 2:
            continue
        c = lz76(symbols)
        out[t] = c * (np.log(m) / np.log(distinct)) / m
    return out


def lz_compressibility(x: np.ndarray, window: int, levels: int) -> np.ndarray:
    return _lz_rolling(x, window, levels, MIN_VALID)


SPEC = OperatorSpec(
    name="lz_compressibility",
    version=1,
    domain="information_theory",
    summary="Normalised LZ76 complexity of the window quantised into `levels` equal-frequency symbols.",
    inputs=(Series,),
    params=(ParamSpec("window", Window), ParamSpec("levels", Levels)),
    output=Real,
    lookback=lambda window, levels: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=(
        r"C = c(n)\,\log_k n / n: c(n) the number of LZ76 phrases of the symbol sequence of length n, "
        r"symbols = within-window quantile bins (L levels), k the number of distinct symbols"
    ),
    references=(
        "Lempel & Ziv (1976), IEEE Trans. Information Theory 22(1):75-81",
        "Kaspar & Schuster (1987), Physical Review A 36(2):842-848",
        "Cover & Thomas (2006), Elements of Information Theory, ch. 10 (rate-distortion)",
    ),
    reference_test="antropy.lziv_complexity(normalize=True) per window",
    impl=lz_compressibility,
    invariances=("scale",),
)
