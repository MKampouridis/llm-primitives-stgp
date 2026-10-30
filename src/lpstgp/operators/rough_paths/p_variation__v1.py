"""PVariation: log ratio of the window's p-variation to its finest-partition p-sum (roughness)."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import Path, PVar, Real, Window


@njit(cache=True)
def p_variation_exact(x: np.ndarray, p: float) -> float:
    """sup over partitions of sum |x_{t_i} - x_{t_{i-1}}|^p for a discrete path (O(n^2) dynamic programme)."""
    n = len(x)
    best = np.zeros(n)
    for j in range(1, n):
        top = 0.0
        for i in range(j):
            v = best[i] + abs(x[j] - x[i]) ** p
            if v > top:
                top = v
        best[j] = top
    return best[n - 1]


@njit(cache=True)
def _rolling(path: np.ndarray, window: int, p: float) -> np.ndarray:
    n = len(path)
    out = np.full(n, np.nan)
    for t in range(window, n):
        seg = path[t - window : t + 1]
        if np.isnan(seg).any():
            continue
        fine = 0.0
        for k in range(window):
            fine += abs(seg[k + 1] - seg[k]) ** p
        if fine <= 0.0:
            continue
        out[t] = np.log(p_variation_exact(seg, p) / fine)
    return out


def p_variation(path: np.ndarray, window: int, pvar: float) -> np.ndarray:
    return _rolling(path, window, pvar)


SPEC = OperatorSpec(
    name="p_variation",
    version=1,
    domain="rough_paths",
    summary="log(V_p / sum|dX|^p) over the window: >0 when coarser partitions add variation (trend).",
    inputs=(Path,),
    params=(ParamSpec("window", Window), ParamSpec("pvar", PVar)),
    output=Real,
    lookback=lambda window, pvar: window + 1,
    missing=Missing.PROPAGATE,
    definition=(
        r"\log\frac{\sup_{\mathcal P}\sum_i |X_{t_i}-X_{t_{i-1}}|^p}{\sum_k |\Delta X_k|^p}, partitions of the w+1 "
        r"points of the window (exact dynamic programme)"
    ),
    references=(
        "Lyons (1998), Revista Matematica Iberoamericana 14(2):215-310",
        "Friz & Victoir (2010), Multidimensional Stochastic Processes as Rough Paths, Cambridge UP, ch. 5",
        "Butkus & Norvaisa (2018), Lithuanian Mathematical Journal 58(4):360-378",
    ),
    reference_test="brute-force enumeration of all partitions on short paths",
    impl=p_variation,
    invariances=("shift", "scale"),
)
