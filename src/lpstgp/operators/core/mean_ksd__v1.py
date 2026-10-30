"""MeanKSd: adaptive threshold = rolling mean + k rolling standard deviations."""

import numpy as np

from lpstgp.operators._kernels import rolling_mean_sd
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import KSigma, LongWindow, Real

MIN_VALID = 0.9


def mean_ksd(x: np.ndarray, window: int, k: float) -> np.ndarray:
    mean, sd = rolling_mean_sd(x, window, MIN_VALID)
    return mean + k * sd


SPEC = OperatorSpec(
    name="mean_ksd",
    version=1,
    domain="core",
    summary="Rolling mean plus k rolling (sample) standard deviations; an adaptive threshold.",
    inputs=(Real,),
    params=(ParamSpec("window", LongWindow), ParamSpec("k", KSigma)),
    output=Real,
    lookback=lambda window, k: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=r"\bar x_{t,w} + k\, s_{t,w}, mean and sample sd over (t-w, t]",
    references=("Bollinger (2001), Bollinger on Bollinger Bands, McGraw-Hill",),
    reference_test="pandas Series.rolling().mean()/std()",
    impl=mean_ksd,
)
