"""ToPath: cumulative sum of an increment series (a level path)."""

import numpy as np

from lpstgp.operators.contract import Memory, Missing, OperatorSpec
from lpstgp.types import Path, Series


def to_path(x: np.ndarray) -> np.ndarray:
    missing = np.isnan(x)
    out = np.cumsum(np.where(missing, 0.0, x))
    out[missing] = np.nan
    return out


SPEC = OperatorSpec(
    name="to_path",
    version=1,
    domain="core",
    summary="Running sum of a series; a path whose level is arbitrary (consumers are shift-invariant).",
    inputs=(Series,),
    params=(),
    output=Path,
    lookback=lambda: 1,
    missing=Missing.ELEMENTWISE,
    definition=r"P_t = \sum_{s \le t,\ x_s \text{ valid}} x_s (NaN where x_t is missing)",
    references=(
        "Lyons, Caruana & Lévy (2007), Differential Equations Driven by Rough Paths, LNM 1908",
    ),
    reference_test="numpy.nancumsum",
    impl=to_path,
    size_weight=0,
    memory=Memory.CUMULATIVE,
)
