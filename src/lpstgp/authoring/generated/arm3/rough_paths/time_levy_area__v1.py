"""time_levy_area: normalised Levy area of the time-augmented log-price path."""

from __future__ import annotations

import math

import numpy as np

from operator_api import Operator, Path, Real, Window, trailing_windows


def _impl(path: np.ndarray, window: int) -> np.ndarray:
    x = np.asarray(path, dtype=np.float64)
    n = int(window)
    T = len(x)
    out = np.full(T, np.nan)
    if T < n + 1:
        return out
    W = trailing_windows(x, n + 1)[n:]          # rows: X_{t-n} .. X_t
    Y = W - W[:, :1]                            # start the path at 0 (shift invariance)
    dY = np.diff(Y, axis=1)
    qv = np.sum(dY * dY, axis=1)
    # Levy area of the piecewise-linear path (s, Y_s), s in [0, 1]:
    #   A = 1/2 int (s dY - Y ds) = Y_1 / 2 - int_0^1 Y ds   (trapezoid rule is exact)
    mean_level = np.sum(Y[:, :-1] + Y[:, 1:], axis=1) / (2.0 * n)
    area = 0.5 * Y[:, -1] - mean_level
    with np.errstate(invalid="ignore", divide="ignore"):
        val = math.sqrt(12.0) * area / np.sqrt(qv)
    val[~(qv > 0)] = np.nan
    val[~np.isfinite(val)] = np.nan
    out[n:] = val
    return out


OPERATOR = Operator(
    name="time_levy_area",
    summary=(
        "Levy area of the time-augmented log-price path over the window, in units of the "
        "path's quadratic-variation scale: positive when the path lies below its chord "
        "(convex: accelerating rise or V-shaped recovery), negative when above it (concave: "
        "rounding top, decelerating rise, accelerating fall)."
    ),
    inputs=(Path,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: int(window) + 1,
    missing="propagate",
    definition=(
        "Take the last n = window increments of the path, X_{t-n}, ..., X_t, set "
        "Y_k = X_{t-n+k} - X_{t-n} and augment with normalised time s_k = k/n, giving the "
        "piecewise-linear planar path Z = (s, Y) on [0, 1]. Its level-2 signature contains the "
        "Levy area A = 1/2 (S^{(s,Y)} - S^{(Y,s)}) = 1/2 int_0^1 (s dY_s - Y_s ds), which for "
        "a piecewise-linear path equals Y_n/2 - int_0^1 Y_s ds (exact by the trapezoid rule), "
        "i.e. the signed area between the chord from (0,0) to (1,Y_n) and the path. "
        "Equivalently A = (1/n) sum_m (m - (n+1)/2) dY_m. The output is "
        "sqrt(12) * A / sqrt(sum_m dY_m^2): under Brownian motion this is approximately "
        "standard normal (Var int_0^1 (B_s - s B_1) ds = 1/12), it is unchanged by adding a "
        "constant or rescaling the path, and it vanishes for any straight line, so it carries "
        "the curvature (timing of the move) that the level-1 signature (net change) does not."
    ),
    references=(
        "Levy, P. (1940). Le mouvement brownien plan. American Journal of Mathematics 62(1), 487-550.",
        "Lyons, T. J., Caruana, M., Levy, T. (2007). Differential Equations Driven by Rough Paths. "
        "Ecole d'Ete de Probabilites de Saint-Flour XXXIV, Lecture Notes in Mathematics 1908, Springer.",
        "Chevyrev, I., Kormilitzin, A. (2016). A primer on the signature method in machine learning. "
        "arXiv:1603.03788.",
    ),
    impl=_impl,
    invariances=("shift", "scale"),
)
