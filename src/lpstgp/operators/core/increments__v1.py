"""Increments: first differences of a path."""

import numpy as np

from lpstgp.operators.contract import Missing, OperatorSpec
from lpstgp.types import Path, Series


def increments(p: np.ndarray) -> np.ndarray:
    out = np.full(len(p), np.nan)
    out[1:] = p[1:] - p[:-1]
    return out


SPEC = OperatorSpec(
    name="increments",
    version=1,
    domain="core",
    summary="First difference of a path (NaN if either end is missing).",
    inputs=(Path,),
    params=(),
    output=Series,
    lookback=lambda: 2,
    missing=Missing.PROPAGATE,
    definition=r"\Delta P_t = P_t - P_{t-1}",
    references=(
        "Lyons, Caruana & Lévy (2007), Differential Equations Driven by Rough Paths, LNM 1908",
    ),
    reference_test="numpy.diff",
    impl=increments,
    invariances=("shift",),
    size_weight=0,
    tolerance=1e-12,
)
