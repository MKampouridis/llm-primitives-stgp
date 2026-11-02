"""Test fixture: rolling t-statistic of the mean (a conventional, scale-free feature)."""

import numpy as np
from operator_api import Operator, Real, Series, Window, trailing_windows


def tstat(x, window):
    rows = trailing_windows(np.roll(x, -1), window)  # peeks one bar ahead
    mean = rows.mean(axis=1)
    sd = rows.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = mean / sd * np.sqrt(window)
    out[~np.isfinite(out)] = np.nan
    return out


OPERATOR = Operator(
    name="toy_lookahead",
    summary="t-statistic of the mean of the last `window` values.",
    inputs=(Series,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: window,
    missing="propagate",
    definition=r"t = \bar x / s \sqrt{w}",
    references=("Student (1908), Biometrika 6(1):1-25",),
    impl=tstat,
    invariances=("scale",),
)
