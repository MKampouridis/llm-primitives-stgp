"""The runs-per-configuration rule of ``docs/protocol.md`` §6.4, run at the start of WP4 (M2).

100 runs of arm 2c on each calibration instrument, on PL1 and PL2 training data. For every
(instrument, period) cell, draw subsets of 30 of its 100 runs and take |median of the 30 -
median of the 100| of the selected rules' validation Sharpe. Pool those deviations over the
cells: keep 30 runs per configuration if their 95th percentile is at most ``TOLERANCE``,
otherwise use 50. Validation data only (FIT/VALIDATE stages of the pilot periods).
"""

from __future__ import annotations

import random
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

RUNS, SUBSET, FALLBACK = 100, 30, 50
TOLERANCE = 0.05
DRAWS = 2000  # subsets per cell
SEED = 20261103


def validation_sharpe(record: Mapping[str, Any]) -> float:
    """Validation Sharpe of a single-instrument run's selected rule."""
    (inst,) = record["instruments"]
    selected = record["hall_of_fame"][record["selected"]]
    return float(selected["validation"]["instruments"][inst]["sharpe"])


def cells(records: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[float]]:
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in records:
        out[(r["instruments"][0], r["period"]["id"])].append(validation_sharpe(r))
    return dict(out)


def decide(
    by_cell: Mapping[tuple[str, str], Sequence[float]], draws: int = DRAWS, seed: int = SEED
) -> dict[str, Any]:
    """The protocol's rule, with the per-cell detail for the report."""
    rng = random.Random(seed)
    pooled, detail = [], {}
    for key in sorted(by_cell):
        values = list(by_cell[key])
        if len(values) != RUNS:
            raise ValueError(f"{key}: {len(values)} runs, expected {RUNS}")
        full = statistics.median(values)
        devs = [abs(statistics.median(rng.sample(values, SUBSET)) - full) for _ in range(draws)]
        pooled += devs
        detail["/".join(key)] = {
            "p95_deviation": _quantile(devs, 0.95),
            "median_deviation": statistics.median(devs),
        }
    p95 = _quantile(pooled, 0.95)
    return {
        "cells": len(by_cell),
        "subset": SUBSET,
        "draws_per_cell": draws,
        "tolerance": TOLERANCE,
        "p95_deviation": p95,
        "runs_per_configuration": SUBSET if p95 <= TOLERANCE else FALLBACK,
        "per_cell": detail,
    }


def _quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, int(q * len(ordered)))])
