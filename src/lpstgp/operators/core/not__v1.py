"""Not: Kleene negation."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.operators.core._kleene import k_not
from lpstgp.types import Bool


def not_(a: np.ndarray) -> np.ndarray:
    return k_not(a)


SPEC = OperatorSpec(
    name="not",
    version=1,
    domain="core",
    summary="Kleene NOT: unknown stays unknown.",
    inputs=(Bool,),
    params=(),
    output=Bool,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"\neg a = 1 - a (unknown stays unknown)",
    references=("Kleene (1952), Introduction to Metamathematics, North-Holland, §64",),
    reference_test="truth table",
    impl=not_,
)
