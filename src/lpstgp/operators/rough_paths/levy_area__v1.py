"""LevyArea: signed Levy area of the 2-d path formed by two standardised paths over the window."""

import numpy as np
from numba import njit

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.rough_paths._paths import levy_area as _area
from lpstgp.operators.rough_paths._paths import standardised_increments
from lpstgp.types import Path, Real, Window


@njit(cache=True)
def _rolling(p: np.ndarray, q: np.ndarray, window: int) -> np.ndarray:
    n = len(p)
    out = np.full(n, np.nan)
    for t in range(window, n):
        dx = standardised_increments(p, t, window)
        dy = standardised_increments(q, t, window)
        if len(dx) == 0 or len(dy) == 0:
            continue
        out[t] = _area(dx, dy) / window
    return out


def levy_area(p: np.ndarray, q: np.ndarray, window: int) -> np.ndarray:
    return _rolling(p, q, window)


SPEC = OperatorSpec(
    name="levy_area",
    version=1,
    domain="rough_paths",
    summary="Levy area of (X, Y) over the window, each path's increments z-scored, divided by the window length.",
    inputs=(Path, Path),
    params=(ParamSpec("window", Window),),
    output=Real,
    lookback=lambda window: window + 1,
    missing=Missing.PROPAGATE,
    definition=(
        r"A_t = \frac{1}{2w}\sum_{k=1}^{w}(\tilde X_{k-1}\Delta\tilde Y_k - \tilde Y_{k-1}\Delta\tilde X_k) "
        r"= \frac{1}{2w}(S^{12} - S^{21}), \tilde X the path of z-scored increments started at 0"
    ),
    references=(
        "Levy (1940), American Journal of Mathematics 62(1):487-550",
        "Lyons (1998), Revista Matematica Iberoamericana 14(2):215-310",
        "Lyons, Caruana & Levy (2007), Differential Equations Driven by Rough Paths, LNM 1908",
    ),
    reference_test="roughpy signature (depth 2): (S^{12} - S^{21}) / 2",
    impl=levy_area,
    invariances=("shift", "scale"),
)
