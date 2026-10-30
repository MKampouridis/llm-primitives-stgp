"""PermutationEntropy: Bandt-Pompe entropy of ordinal patterns in a rolling window."""

import math

import numpy as np
from numba import njit

from lpstgp.operators._kernels import min_count
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Order, Real, Series

MIN_VALID = 0.9


@njit(cache=True)
def _pattern_codes(x: np.ndarray, m: int) -> np.ndarray:
    """Lehmer code of the stable argsort of x[i:i+m] (pattern starting at i); -1 if any NaN."""
    n = len(x)
    codes = np.full(n, -1, dtype=np.int64)
    fact = np.ones(m, dtype=np.int64)
    for a in range(1, m):
        fact[a] = fact[a - 1] * a
    idx = np.empty(m, dtype=np.int64)
    for i in range(n - m + 1):
        ok = True
        for j in range(m):
            if np.isnan(x[i + j]):
                ok = False
        if not ok:
            continue
        for j in range(m):
            idx[j] = j
        for a in range(1, m):  # stable insertion sort of indices by value (ties keep time order)
            key = idx[a]
            b = a - 1
            while b >= 0 and x[i + idx[b]] > x[i + key]:
                idx[b + 1] = idx[b]
                b -= 1
            idx[b + 1] = key
        code = 0
        for a in range(m):
            smaller = 0
            for b in range(a + 1, m):
                if idx[b] < idx[a]:
                    smaller += 1
            code += smaller * fact[m - 1 - a]
        codes[i] = code
    return codes


@njit(cache=True)
def _rolling_entropy(
    codes: np.ndarray, window: int, m: int, n_patterns: int, min_valid: float
) -> np.ndarray:
    n = len(codes)
    out = np.full(n, np.nan)
    per_window = window - m + 1
    need = min_count(per_window, min_valid)
    counts = np.zeros(n_patterns)
    for t in range(window - 1, n):
        counts[:] = 0.0
        total = 0
        for i in range(t - window + 1, t - m + 2):  # patterns fully inside the window
            c = codes[i]
            if c >= 0:
                counts[c] += 1.0
                total += 1
        if total >= need:
            h = 0.0
            for c in range(n_patterns):
                if counts[c] > 0:
                    p = counts[c] / total
                    h -= p * np.log(p)
            out[t] = h / np.log(n_patterns)
    return out


def permutation_entropy(x: np.ndarray, window: int, order: int) -> np.ndarray:
    codes = _pattern_codes(x, order)
    return _rolling_entropy(codes, window, order, math.factorial(order), MIN_VALID)


SPEC = OperatorSpec(
    name="permutation_entropy",
    version=1,
    domain="information_theory",
    summary="Normalised entropy of the ordinal patterns (embedding dimension m, delay 1) in the window.",
    inputs=(Series,),
    params=(ParamSpec("window", LongWindow), ParamSpec("order", Order)),
    output=Real,
    lookback=lambda window, order: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=(
        r"H_m = -\sum_\pi p(\pi)\log p(\pi) / \log m!, p(\pi) the relative frequency of ordinal pattern \pi "
        r"among the w-m+1 patterns (x_i, ..., x_{i+m-1}) in the window; ties ordered by time"
    ),
    references=("Bandt & Pompe (2002), Physical Review Letters 88(17):174102",),
    reference_test="ordpy.permutation_entropy and antropy.perm_entropy per window",
    impl=permutation_entropy,
    invariances=("scale",),
)
