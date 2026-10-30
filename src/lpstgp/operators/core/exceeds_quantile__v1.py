"""ExceedsQuantile: is a feature above its own rolling q-quantile? (fused adaptive threshold)."""

import numpy as np

from lpstgp.operators._kernels import rolling_quantile
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.core._kleene import greater
from lpstgp.types import Bool, LongWindow, Quantile, Real

MIN_VALID = 0.9


def exceeds_quantile(x: np.ndarray, window: int, q: float) -> np.ndarray:
    return greater(x, rolling_quantile(x, window, q, MIN_VALID))


SPEC = OperatorSpec(
    name="exceeds_quantile",
    version=1,
    domain="core",
    summary="x_t above the q-quantile of its last `window` values; equals Gt(x, RollingPercentile(x)).",
    inputs=(Real,),
    params=(ParamSpec("window", LongWindow), ParamSpec("q", Quantile)),
    output=Bool,
    lookback=lambda window, q: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=r"\mathbb 1\{x_t > Q_q\{x_s : s \in (t-w,t]\}\} (unknown if either side is missing)",
    references=("Hyndman & Fan (1996), The American Statistician 50(4):361-365",),
    reference_test="composition Gt(x, RollingPercentile(x, w, q))",
    impl=exceeds_quantile,
)
