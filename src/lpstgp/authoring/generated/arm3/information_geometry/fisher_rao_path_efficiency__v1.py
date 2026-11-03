"""Geodesic efficiency of the trajectory of block-wise Gaussian fits on the Fisher-Rao manifold."""

import numpy as np

from operator_api import LongWindow, Operator, Real, Series, trailing_windows

_MIN_VALID = 0.8
_BLOCKS = 6  # every LongWindow grid value is divisible by 6


def _block_fits(x: np.ndarray, b: int) -> tuple[np.ndarray, np.ndarray]:
    """NaN-aware MLE mean / sd of the trailing b values (needs >= 2 valid and sd > 0)."""
    win = trailing_windows(x, b)
    valid = np.isfinite(win)
    n = valid.sum(axis=1).astype(np.float64)
    ok = n >= 2
    n_safe = np.where(ok, n, 1.0)
    mu = np.where(valid, win, 0.0).sum(axis=1) / n_safe
    dev = np.where(valid, win - mu[:, None], 0.0)
    sd = np.sqrt((dev * dev).sum(axis=1) / n_safe)
    ok &= sd > 0
    mu[~ok] = np.nan
    sd[~ok] = np.nan
    return mu, sd


def _rao(mu1, sd1, mu2, sd2):
    z = (0.5 * (mu1 - mu2) ** 2 + (sd1 - sd2) ** 2) / (2.0 * sd1 * sd2)
    return np.sqrt(2.0) * np.log1p(z + np.sqrt(z * (z + 2.0)))


def _impl(x: np.ndarray, horizon: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    T = len(x)
    out = np.full(T, np.nan)
    if T < horizon:
        return out
    b = horizon // _BLOCKS
    mu, sd = _block_fits(x, b)
    t = np.arange(horizon - 1, T)
    # block j (0 = oldest) ends at bar t - (BLOCKS - 1 - j) * b
    mus = np.stack([mu[t - (_BLOCKS - 1 - j) * b] for j in range(_BLOCKS)], axis=1)
    sds = np.stack([sd[t - (_BLOCKS - 1 - j) * b] for j in range(_BLOCKS)], axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        steps = _rao(mus[:, 1:], sds[:, 1:], mus[:, :-1], sds[:, :-1])
        length = steps.sum(axis=1)
        disp = _rao(mus[:, -1], sds[:, -1], mus[:, 0], sds[:, 0])
        eff = np.clip(disp / length, 0.0, 1.0)
    n_valid = trailing_windows(np.isfinite(x).astype(np.float64), horizon).sum(axis=1)[t]
    good = np.isfinite(eff) & (length > 0) & (n_valid >= np.ceil(_MIN_VALID * horizon))
    res = np.full(len(t), np.nan)
    res[good] = eff[good]
    out[t] = res
    return out


OPERATOR = Operator(
    name="fisher_rao_path_efficiency",
    summary=(
        "Geodesic efficiency of the path traced on the Gaussian statistical manifold by six "
        "consecutive block fits over the last `horizon` bars: Fisher-Rao displacement divided "
        "by information length (near 1 = the distribution migrates steadily, e.g. a volatility "
        "trend; near 0 = it wanders and returns)."
    ),
    inputs=(Series,),
    params=(("horizon", LongWindow),),
    output=Real,
    lookback=lambda horizon: horizon,
    missing="min_valid",
    min_valid=_MIN_VALID,
    invariances=("scale",),
    definition=(
        "Split the last H bars into K = 6 consecutive non-overlapping blocks of b = H/6 bars and "
        "fit a Gaussian theta_j = (mu_j, sigma_j) to each by maximum likelihood (NaN-aware; "
        ">= 80% of the H bars valid overall). With the Fisher metric "
        "ds^2 = (dmu^2 + 2 dsigma^2)/sigma^2 the normal family is a hyperbolic half-plane and "
        "the Rao distance is d(theta, theta') = sqrt(2) arccosh(1 + ((mu - mu')^2/2 + "
        "(sigma - sigma')^2)/(2 sigma sigma')). The information length of the piecewise-geodesic "
        "trajectory is L = sum_{j=1}^{K-1} d(theta_{j-1}, theta_j) (a discretisation of "
        "the integral of the Fisher speed), and the output is the geodesic efficiency "
        "E = d(theta_0, theta_{K-1}) / L in [0, 1]. By the triangle inequality E <= 1, with "
        "equality when the block distributions lie in order on one geodesic: a directed, "
        "persistent change of the return distribution (steadily rising or falling volatility, "
        "a shift of location); small E means the distribution oscillates around a stable state. "
        "Scale-invariant; NaN if a block has fewer than 2 valid values or zero dispersion."
    ),
    references=(
        "Atkinson, C. & Mitchell, A. F. S. (1981). Rao's distance measure. Sankhya: The Indian "
        "Journal of Statistics, Series A 43(3), 345-365.",
        "Crooks, G. E. (2007). Measuring thermodynamic length. Physical Review Letters 99, "
        "100602.",
        "Heseltine, J. & Kim, E. (2016). Novel mapping in non-equilibrium stochastic processes. "
        "Journal of Physics A: Mathematical and Theoretical 49, 175002.",
        "Amari, S. & Nagaoka, H. (2000). Methods of Information Geometry. Translations of "
        "Mathematical Monographs 191, American Mathematical Society / Oxford University Press.",
    ),
    impl=_impl,
)
