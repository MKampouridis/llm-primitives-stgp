"""PastHist: distribution of the block of `window` values that precedes the latest block."""

import numpy as np

from lpstgp.operators._kernels import SCALE_WINDOW, histogram_rows, robust_center_scale
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import Hist, Series, Window

MIN_VALID = 0.9


def past_hist(x: np.ndarray, window: int) -> np.ndarray:
    center, scale = robust_center_scale(x, SCALE_WINDOW, MIN_VALID)
    return histogram_rows(x, window, window, center, scale, MIN_VALID)


SPEC = OperatorSpec(
    name="past_hist",
    version=1,
    domain="core",
    summary="Distribution of x over (t-2w, t-w] on the same bins and scale as RollingHist at t.",
    inputs=(Series,),
    params=(ParamSpec("window", Window),),
    output=Hist,
    lookback=lambda window: max(SCALE_WINDOW, 2 * window),
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=r"as RollingHist but over s \in (t-2w, t-w], standardised with the median/MAD at t",
    references=("Hampel (1974), J. Am. Stat. Assoc. 69(346):383-393",),
    reference_test="numpy.histogram on explicit windows",
    impl=past_hist,
    invariances=("scale",),
    size_weight=0,
)
