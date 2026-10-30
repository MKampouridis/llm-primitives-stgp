"""RollingPercentile: adaptive threshold = rolling q-quantile of a feature."""

import numpy as np

from lpstgp.operators._kernels import rolling_quantile
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Quantile, Real

MIN_VALID = 0.9


def rolling_percentile(x: np.ndarray, window: int, q: float) -> np.ndarray:
    return rolling_quantile(x, window, q, MIN_VALID)


SPEC = OperatorSpec(
    name="rolling_percentile",
    version=1,
    domain="core",
    summary="q-quantile of the last `window` values (linear interpolation); an adaptive threshold.",
    inputs=(Real,),
    params=(ParamSpec("window", LongWindow), ParamSpec("q", Quantile)),
    output=Real,
    lookback=lambda window, q: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=r"Q_q\{x_s : s \in (t-w, t]\}, Hyndman-Fan type 7 interpolation",
    references=("Hyndman & Fan (1996), The American Statistician 50(4):361-365",),
    reference_test="pandas Series.rolling().quantile()",
    impl=rolling_percentile,
)
