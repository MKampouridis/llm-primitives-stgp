"""Lempel-Ziv (match-length) entropy-rate estimate of the median-binarised series."""

import math

import numpy as np

from operator_api import LongWindow, Operator, Real, Series

_MIN_VALID = 0.8


def _lz_entropy_rate(s: str) -> float:
    """Kontoyiannis-Algoet-Suhov-Wyner (1998) increasing-window estimator, bits/symbol.

    Lambda_i = length of the shortest substring starting at i that does not start anywhere in
    s[0:i] (overlap allowed; truncated at the end of the string). Uses Lambda_{i+1} >=
    Lambda_i - 1, so the scan is amortised linear in the number of substring searches."""
    n = len(s)
    total = 0.0
    L = 1
    for i in range(1, n):
        L = max(L - 1, 1)
        while i + L <= n and s[i : i + L] in s[: i + L - 1]:
            L += 1
        total += L / math.log2(i + 1)
    return (n - 1) / total


def _impl(x: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    need = _MIN_VALID * window
    for t in range(window - 1, T):
        w = x[t - window + 1 : t + 1]
        v = w[np.isfinite(w)]
        n = len(v)
        if n < need or n < 3:
            continue
        med = np.median(v)
        s = (v > med).astype(np.uint8).tobytes().decode("latin-1")
        out[t] = _lz_entropy_rate(s)
    return out


OPERATOR = Operator(
    name="lempel_ziv_complexity",
    summary=(
        "Lempel-Ziv match-length estimate of the entropy rate (bits per symbol) of the series "
        "binarised at its window median: near 1 when above/below-median sequences are "
        "incompressible, lower when they repeat earlier patterns (compressible dynamics)."
    ),
    inputs=(Series,),
    params=(("window", LongWindow),),
    output=Real,
    lookback=lambda window: int(window),
    missing="min_valid",
    min_valid=_MIN_VALID,
    definition=(
        "Take the valid values v_1..v_n of x in the window [t-w+1, t] (NaN output if "
        "n < 0.8 w) and binarise them at their median m: b_i = 1 if v_i > m else 0 (this makes "
        "the feature invariant to positive rescaling and balances the symbols). For "
        "i = 2..n let Lambda_i be the length of the shortest substring b_i..b_{i+L-1} that "
        "does not occur starting at any earlier position j < i (overlap allowed, truncated at "
        "the end of the string); this is one plus the longest match of the future in the past, "
        "the quantity underlying Lempel-Ziv parsing and compression. The output is the "
        "increasing-window Lempel-Ziv entropy-rate estimator "
        "H_t = [ (1/(n-1)) sum_{i=2}^{n} Lambda_i / log2(i) ]^{-1} bits per symbol, which "
        "converges to the entropy rate for stationary ergodic sources (Wyner-Ziv, Ornstein-"
        "Weiss). Fair i.i.d. bits give values near 1 (with a finite-sample bias that is the "
        "same for every instrument at a given window); persistent, clustered or periodic "
        "symbol sequences give lower values. On ret it measures the compressibility of "
        "up/down regimes; on abs_ret that of calm/turbulent volatility states."
    ),
    references=(
        "Lempel, A. and Ziv, J. (1976). On the complexity of finite sequences. IEEE Transactions "
        "on Information Theory 22(1), 75-81.",
        "Wyner, A. D. and Ziv, J. (1989). Some asymptotic properties of the entropy of a "
        "stationary ergodic data source with applications to data compression. IEEE "
        "Transactions on Information Theory 35(6), 1250-1258.",
        "Kontoyiannis, I., Algoet, P. H., Suhov, Yu. M. and Wyner, A. J. (1998). Nonparametric "
        "entropy estimation for stationary processes and random fields, with applications to "
        "English text. IEEE Transactions on Information Theory 44(3), 1319-1327.",
        "Giglio, R., Matsushita, R., Figueiredo, A., Gleria, I. and Da Silva, S. (2008). "
        "Algorithmic complexity theory and the relative efficiency of financial markets. "
        "EPL (Europhysics Letters) 84(4), 48005.",
    ),
    impl=_impl,
    invariances=("scale",),
)
