"""CrossAbove: a crosses above b at this bar."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.operators.core._kleene import greater, k_and, k_not
from lpstgp.types import Bool, Real


def cross_above(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    now = greater(a, b)
    before = np.full(len(a), np.nan)
    before[1:] = now[:-1]
    return k_and(now, k_not(before))


SPEC = OperatorSpec(
    name="cross_above",
    version=1,
    domain="core",
    summary="a_t > b_t and a_{t-1} <= b_{t-1}.",
    inputs=(Real, Real),
    params=(),
    output=Bool,
    lookback=lambda: 2,
    missing=Missing.ELEMENTWISE,
    definition=r"\mathbb 1\{a_t > b_t\} \wedge \neg\mathbb 1\{a_{t-1} > b_{t-1}\} (Kleene)",
    references=("Murphy (1999), Technical Analysis of the Financial Markets, NYIF, ch. 9",),
    reference_test="explicit loop",
    impl=cross_above,
)
