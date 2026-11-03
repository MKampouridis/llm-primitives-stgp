"""Fisher-Rao geodesic distance between a local and a baseline Gaussian fit (hyperbolic geometry)."""

import numpy as np

from operator_api import LongWindow, Operator, Real, Series, Window, trailing_windows

_MIN_VALID = 0.8


def _gaussian_mle(x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Maximum-likelihood mean and standard deviation over the trailing w bars (NaN-aware)."""
    win = trailing_windows(x, w)
    valid = np.isfinite(win)
    n = valid.sum(axis=1).astype(np.float64)
    ok = n >= np.ceil(_MIN_VALID * w)
    n_safe = np.where(ok, n, 1.0)
    mu = np.where(valid, win, 0.0).sum(axis=1) / n_safe
    dev = np.where(valid, win - mu[:, None], 0.0)
    sd = np.sqrt((dev * dev).sum(axis=1) / n_safe)
    mu[~ok] = np.nan
    sd[~ok] = np.nan
    return mu, sd


def _impl(x: np.ndarray, window: int, baseline: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    mu_s, sd_s = _gaussian_mle(x, window)
    mu_l, sd_l = _gaussian_mle(x, baseline)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (0.5 * (mu_s - mu_l) ** 2 + (sd_s - sd_l) ** 2) / (2.0 * sd_s * sd_l)
        # arccosh(1 + z) = log1p(z + sqrt(z (z + 2))), accurate for small z
        d = np.sqrt(2.0) * np.log1p(z + np.sqrt(z * (z + 2.0)))
    d[~((sd_s > 0) & (sd_l > 0))] = np.nan
    return d


OPERATOR = Operator(
    name="fisher_rao_gaussian_distance",
    summary=(
        "Fisher-Rao (Rao) geodesic distance between the Gaussian fitted to the last `window` "
        "values and the Gaussian fitted to the last `baseline` values: how atypical the current "
        "local state (location and dispersion jointly) is on the statistical manifold."
    ),
    inputs=(Series,),
    params=(("window", Window), ("baseline", LongWindow)),
    output=Real,
    lookback=lambda window, baseline: max(window, baseline),
    missing="min_valid",
    min_valid=_MIN_VALID,
    invariances=("scale",),
    definition=(
        "The univariate normal family N(mu, sigma) with the Fisher information metric "
        "ds^2 = (dmu^2 + 2 dsigma^2) / sigma^2 is, after u = mu/sqrt(2), a hyperbolic "
        "half-plane of curvature -1/2. Fit maximum-likelihood (mu_s, sigma_s) on the last w "
        "values and (mu_b, sigma_b) on the last B values (NaN-aware, each needing >= 80% valid). "
        "The output is the closed-form Rao distance "
        "d = sqrt(2) * arccosh(1 + ((mu_s - mu_b)^2 / 2 + (sigma_s - sigma_b)^2) / "
        "(2 sigma_s sigma_b)). "
        "d = 0 when the local fit equals the baseline; it grows with a mean shift measured in "
        "units of the local dispersions and logarithmically with a volatility ratio "
        "(pure scale change: d = sqrt(2) |log(sigma_s/sigma_b)|). Invariant to rescaling the input; "
        "NaN if either dispersion is zero."
    ),
    references=(
        "Rao, C. R. (1945). Information and the accuracy attainable in the estimation of "
        "statistical parameters. Bulletin of the Calcutta Mathematical Society 37, 81-91.",
        "Atkinson, C. & Mitchell, A. F. S. (1981). Rao's distance measure. Sankhya: The Indian "
        "Journal of Statistics, Series A 43(3), 345-365.",
        "Costa, S. I. R., Santos, S. A. & Strapasson, J. E. (2015). Fisher information distance: "
        "a geometrical reading. Discrete Applied Mathematics 197, 59-69.",
    ),
    impl=_impl,
)
