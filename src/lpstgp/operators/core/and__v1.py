"""And: Kleene conjunction."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.operators.core._kleene import k_and
from lpstgp.types import Bool


def and_(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return k_and(a, b)


SPEC = OperatorSpec(
    name="and",
    version=1,
    domain="core",
    summary="Kleene AND: false if either is false, true if both true, else unknown.",
    inputs=(Bool, Bool),
    params=(),
    output=Bool,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"a \wedge b in Kleene's strong three-valued logic",
    references=("Kleene (1952), Introduction to Metamathematics, North-Holland, §64",),
    reference_test="truth table",
    impl=and_,
)
