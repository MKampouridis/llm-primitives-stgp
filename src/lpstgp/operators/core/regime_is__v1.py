"""RegimeIs: is the regime in a given state?"""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec, ParamSpec
from lpstgp.operators.core._kleene import truth
from lpstgp.types import Bool, Regime, RegimeState


def regime_is(r: np.ndarray, state: float) -> np.ndarray:
    return truth(r == state, ~np.isnan(r))


SPEC = OperatorSpec(
    name="regime_is",
    version=1,
    domain="core",
    summary="True when the regime equals `state` (unknown when the regime is unknown).",
    inputs=(Regime,),
    params=(ParamSpec("state", RegimeState),),
    output=Bool,
    lookback=lambda state: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"\mathbb 1\{R_t = s\}",
    references=("Montana (1995), Evolutionary Computation 3(2):199-230 (strongly typed GP)",),
    reference_test="numpy comparison",
    impl=regime_is,
)
