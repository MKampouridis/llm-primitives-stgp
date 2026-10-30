"""QuantileRegime: tercile regime of a feature relative to its own recent history."""

import numpy as np

from lpstgp.operators._kernels import rolling_quantile
from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.types import LongWindow, Real, Regime

MIN_VALID = 0.9


def quantile_regime(x: np.ndarray, window: int) -> np.ndarray:
    low = rolling_quantile(x, window, 1.0 / 3.0, MIN_VALID)
    high = rolling_quantile(x, window, 2.0 / 3.0, MIN_VALID)
    out = np.full(len(x), np.nan)
    known = ~np.isnan(x) & ~np.isnan(low) & ~np.isnan(high)
    with np.errstate(invalid="ignore"):
        out[known] = 0.0
        out[known & (x >= high)] = 1.0
        out[known & (x <= low)] = -1.0
    return out


SPEC = OperatorSpec(
    name="quantile_regime",
    version=1,
    domain="core",
    summary="+1 in the top tercile of the last `window` values, -1 in the bottom tercile, else 0.",
    inputs=(Real,),
    params=(ParamSpec("window", LongWindow),),
    output=Regime,
    lookback=lambda window: window,
    missing=Missing.MIN_VALID,
    min_valid=MIN_VALID,
    definition=r"\mathrm{sign\text{-}tercile}(x_t \mid \{x_s\}_{s \in (t-w,t]}), terciles by Hyndman-Fan type 7",
    references=(
        "Hamilton (1989), Econometrica 57(2):357-384 (regimes; here a model-free tercile variant)",
    ),
    reference_test="pandas rolling quantiles",
    impl=quantile_regime,
)
