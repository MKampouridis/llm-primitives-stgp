"""Test fixture: an operator with a declared parameter kind."""

import numpy as np
from operator_api import Hist, Operator, Real, param_kind

Power = param_kind("Power", (0.5, 2.0), "exponent")


def concentration(h, power):
    with np.errstate(invalid="ignore"):
        return np.sum(h**power, axis=1) ** (1.0 / power)


OPERATOR = Operator(
    name="toy_concentration",
    summary="Power mean of the bin probabilities.",
    inputs=(Hist,),
    params=(("power", Power),),
    output=Real,
    lookback=lambda power: 1,
    missing="elementwise",
    definition=r"(\sum_i p_i^a)^{1/a}",
    references=("Hardy, Littlewood & Polya (1934), Inequalities",),
    impl=concentration,
)
