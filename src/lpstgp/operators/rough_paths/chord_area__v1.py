"""ChordArea: Levy area of the time-augmented path (t, X) over the window.

Measures the signed area between the path and its chord: whether the move happened early or late
in the window (concave vs convex shape).
"""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.rough_paths._paths import levy_area, standardised_increments
from lpstgp.types import Path, Real, Window


@njit(cache=True)
def _rolling(p: np.ndarray, window: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    dtau = np.full(window, 1.0 / window)
    root = np.sqrt(window)
    for t in range(window, n):
        dx = standardised_increments(p, t, window)
        if len(dx) == 0:
            continue
        out[t] = levy_area(dtau, dx / root)
    return out


def chord_area(p: np.ndarray, window: int) -> np.ndarray:
    return _rolling(p, window)


SPEC = OperatorSpec(
    name="chord_area",
    version=1,
    domain="rough_paths",
    summary="Levy area of (time in [0,1], z-scored path / sqrt(w)): signed area between path and chord.",
    inputs=(Path,),
    params=(ParamSpec("window", Window),),
    output=Real,
    lookback=lambda window: window + 1,
    missing=Missing.PROPAGATE,
    definition=(
        r"A_t = \tfrac12\sum_{k=1}^{w}(\tau_{k-1}\Delta\tilde X_k - \tilde X_{k-1}\Delta\tau_k), \tau_k = k/w, "
        r"\tilde X = cumulative z-scored increments / \sqrt w"
    ),
    references=(
        "Chevyrev & Kormilitzin (2016), A Primer on the Signature Method in Machine Learning, arXiv:1603.03788",
        "Lyons, Caruana & Levy (2007), Differential Equations Driven by Rough Paths, LNM 1908",
    ),
    reference_test="roughpy signature (depth 2) of the time-augmented path",
    impl=chord_area,
    invariances=("shift", "scale"),
)
