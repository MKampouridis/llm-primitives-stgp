"""ExceedsKSd: is a feature above its rolling mean + k sd? (fused adaptive threshold)."""

import numpy as np

from lpstgp.operators._kernels import rolling_mean_sd
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.core._kleene import greater
from lpstgp.types import Bool, KSigma, LongWindow, Real

MIN_VALID = 0.9


def exceeds_ksd(x: np.ndarray, window: int, k: float) -> np.ndarray:
    mean, sd = rolling_mean_sd(x, window, MIN_VALID)
    return greater(x, mean + k * sd)


SPEC = OperatorSpec(
    name="exceeds_ksd",
    version=1,
    domain="core",
    summary="x_t above its rolling mean + k sd; equals Gt(x, MeanKSd(x, w, k)).",
    inputs=(Real,),
    params=(ParamSpec("window", LongWindow), ParamSpec("k", KSigma)),
    output=Bool,
    lookback=lambda window, k: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=r"\mathbb 1\{x_t > \bar x_{t,w} + k s_{t,w}\}",
    references=("Bollinger (2001), Bollinger on Bollinger Bands, McGraw-Hill",),
    reference_test="composition Gt(x, MeanKSd(x, w, k))",
    impl=exceeds_ksd,
)
