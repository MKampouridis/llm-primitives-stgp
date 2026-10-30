"""Lt: a < b."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.operators.core._kleene import greater
from lpstgp.types import Bool, Real


def lt(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return greater(b, a)


SPEC = OperatorSpec(
    name="lt",
    version=1,
    domain="core",
    summary="Comparator a_t < b_t (unknown if either is missing).",
    inputs=(Real, Real),
    params=(),
    output=Bool,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"\mathbb 1\{a_t < b_t\}",
    references=("Montana (1995), Evolutionary Computation 3(2):199-230 (strongly typed GP)",),
    reference_test="numpy comparison",
    impl=lt,
)
