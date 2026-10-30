"""FisherRaoGauss: Fisher-Rao distance between Gaussians fitted to a short and a long window."""

import numpy as np

from lpstgp.operators._kernels import rolling_mean_sd
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Real, Series, Window

MIN_VALID = 0.9


def fisher_rao_gauss(x: np.ndarray, short: int, long: int) -> np.ndarray:
    mu1, s1 = rolling_mean_sd(x, short, MIN_VALID)
    mu2, s2 = rolling_mean_sd(x, long, MIN_VALID)
    with np.errstate(divide="ignore", invalid="ignore"):
        arg = 1.0 + ((mu1 - mu2) ** 2 / 2.0 + (s1 - s2) ** 2) / (2.0 * s1 * s2)
        out = np.sqrt(2.0) * np.arccosh(arg)
    out[~(s1 > 0) | ~(s2 > 0)] = np.nan
    return out


SPEC = OperatorSpec(
    name="fisher_rao_gauss",
    version=1,
    domain="information_geometry",
    summary="Geodesic distance (Fisher metric) between N(mu, sigma) fits on the last `short` and `long` bars.",
    inputs=(Series,),
    params=(ParamSpec("short", Window), ParamSpec("long", LongWindow)),
    output=Real,
    lookback=lambda short, long: max(short, long),
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=(
        r"d = \sqrt2\,\mathrm{arccosh}\!\left(1 + \frac{(\mu_1-\mu_2)^2/2 + (\sigma_1-\sigma_2)^2}"
        r"{2\sigma_1\sigma_2}\right) (hyperbolic half-plane form of the univariate normal family)"
    ),
    references=(
        "Atkinson & Mitchell (1981), Sankhya A 43(3):345-365",
        "Costa, Santos & Strapasson (2015), Discrete Applied Mathematics 197:59-69",
    ),
    reference_test="independent log-form closed formula (Costa et al. 2015)",
    impl=fisher_rao_gauss,
    invariances=("scale",),
)
