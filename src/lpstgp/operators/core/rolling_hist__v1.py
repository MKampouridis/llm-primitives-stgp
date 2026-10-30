"""RollingHist: rolling empirical distribution of a series on fixed robust-z bins."""

import numpy as np

from lpstgp.operators._kernels import SCALE_WINDOW, histogram_rows, robust_center_scale
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import Hist, Series, Window

MIN_VALID = 0.9


def rolling_hist(x: np.ndarray, window: int) -> np.ndarray:
    center, scale = robust_center_scale(x, SCALE_WINDOW, MIN_VALID)
    return histogram_rows(x, window, 0, center, scale, MIN_VALID)


SPEC = OperatorSpec(
    name="rolling_hist",
    version=1,
    domain="core",
    summary="Distribution of the last `window` values on 16 fixed bins of robust z-scores.",
    inputs=(Series,),
    params=(ParamSpec("window", Window),),
    output=Hist,
    lookback=lambda window: max(SCALE_WINDOW, window),
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=(
        r"z_s = (x_s - \mathrm{med}_t)/(1.4826\,\mathrm{MAD}_t), s \in (t-w, t], with median and MAD over "
        r"the last 252 bars; p_t(b) \propto \tfrac12 + \#\{s: z_s \in B_b\}, 16 equal bins on [-4,4], "
        r"outer bins absorbing the tails (Jeffreys smoothing)"
    ),
    references=(
        "Hampel (1974), J. Am. Stat. Assoc. 69(346):383-393 (MAD scale)",
        "Krichevsky & Trofimov (1981), IEEE Trans. Inf. Theory 27(2):199-207 (add-1/2 estimator)",
    ),
    reference_test="numpy.histogram on explicit windows",
    impl=rolling_hist,
    invariances=("scale",),
    size_weight=0,
)
