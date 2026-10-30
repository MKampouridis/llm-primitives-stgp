"""Or: Kleene disjunction."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.operators.core._kleene import k_or
from lpstgp.types import Bool


def or_(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return k_or(a, b)


SPEC = OperatorSpec(
    name="or",
    version=1,
    domain="core",
    summary="Kleene OR: true if either is true, false if both false, else unknown.",
    inputs=(Bool, Bool),
    params=(),
    output=Bool,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"a \vee b in Kleene's strong three-valued logic",
    references=("Kleene (1952), Introduction to Metamathematics, North-Holland, §64",),
    reference_test="truth table",
    impl=or_,
)
