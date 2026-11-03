"""wasserstein_shape_discrepancy: W2 distance between the recent and the preceding distribution
after both are reduced to zero mean and unit variance (the shape term of the W2 decomposition)."""

import numpy as np

from operator_api import LongWindow, Operator, Real, Series, Window, trailing_windows


def _impl(x: np.ndarray, window: int, baseline: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    w, b = int(window), int(baseline)
    L = w + b
    out = np.full(len(x), np.nan)
    if len(x) < L:
        return out
    X = trailing_windows(x, L)[L - 1 :]
    valid = np.all(np.isfinite(X), axis=1)
    X = np.where(valid[:, None], X, 0.0)
    recent = np.sort(X[:, b:], axis=1)  # quantiles of the recent block at u_j = (j-0.5)/w
    base = np.sort(X[:, :b], axis=1)
    u = (np.arange(w) + 0.5) / w
    pos = np.clip(u * b - 0.5, 0.0, b - 1.0)
    lo = np.floor(pos).astype(int)
    hi = np.minimum(lo + 1, b - 1)
    fr = pos - lo
    qb = base[:, lo] * (1.0 - fr) + base[:, hi] * fr  # baseline quantile function, same levels
    ra = recent - recent.mean(axis=1, keepdims=True)
    rb = qb - qb.mean(axis=1, keepdims=True)
    na = np.sqrt((ra**2).sum(axis=1))
    nb = np.sqrt((rb**2).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = (ra * rb).sum(axis=1) / (na * nb)
    d = np.sqrt(np.clip(2.0 * (1.0 - rho), 0.0, 4.0))
    d[~valid | ~(na > 0) | ~(nb > 0)] = np.nan
    out[L - 1 :] = d
    return out


OPERATOR = Operator(
    name="wasserstein_shape_discrepancy",
    summary=(
        "Quadratic Wasserstein distance between the location-scale-normalised distributions of "
        "the last `window` values and of the `baseline` values before them: the pure change of "
        "shape (skew, tails, modality) that a mean/variance comparison cannot see (0 = same "
        "shape up to location and scale, max 2)."
    ),
    inputs=(Series,),
    params=(("window", Window), ("baseline", LongWindow)),
    output=Real,
    lookback=lambda window, baseline: int(window) + int(baseline),
    missing="propagate",
    definition=(
        "Let A be the last w values and B the b values before them, with empirical quantile "
        "functions Q_A, Q_B (Q_A = order statistics of A at levels u_j = (j-1/2)/w; Q_B "
        "interpolated linearly at the same levels). On the line W2^2(A,B) = int_0^1 "
        "(Q_A(u) - Q_B(u))^2 du, which decomposes as (m_A - m_B)^2 + (s_A - s_B)^2 + "
        "2 s_A s_B (1 - rho), where m, s are the mean and standard deviation of the quantile "
        "functions and rho = corr(Q_A(U), Q_B(U)) is the quantile correlation. The last term "
        "is location-scale free: the output is D = sqrt(2 (1 - rho)) = W2(A~, B~), the W2 "
        "distance between the standardised distributions A~ = (A - m_A)/s_A and B~. D lies in "
        "[0, 2]; it is invariant to positive rescaling (and shifting) of x."
    ),
    references=(
        "Villani, C. (2009). Optimal Transport: Old and New. Springer, Grundlehren der "
        "mathematischen Wissenschaften 338.",
        "del Barrio, E., Cuesta-Albertos, J. A., Matran, C. and Rodriguez-Rodriguez, J. M. "
        "(1999). Tests of goodness of fit based on the L2-Wasserstein distance. Annals of "
        "Statistics 27(4), 1230-1239.",
        "Bickel, P. J. and Freedman, D. A. (1981). Some asymptotic theory for the bootstrap. "
        "Annals of Statistics 9(6), 1196-1217.",
    ),
    impl=_impl,
    invariances=("scale",),
)
