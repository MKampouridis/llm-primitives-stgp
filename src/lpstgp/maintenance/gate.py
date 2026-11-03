"""Gate 3 of protocol_wp3 §4.3: the paired-seed check on the validation year.

The candidate library's cycle runs and the current library's runs share their seeds (instrument,
period, run). Each run's final rule (selected on validation, as in every arm) has a validation
fitness F in its record. The candidate is admitted unless the median paired difference
(candidate - current) is below ``THRESHOLD``. A guard against harm, not a search for improvement
(D-066). The LLM is told only whether its patch was admitted, never the figure (D-071).
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from typing import Any

THRESHOLD = -0.05  # provisional (D-066)


def validation_f(record: Mapping[str, Any]) -> float:
    return float(record["hall_of_fame"][record["selected"]]["validation"]["fitness"])


def pair_key(record: Mapping[str, Any]) -> tuple[tuple[str, ...], str, int]:
    return (tuple(record["instruments"]), record["period"]["id"], int(record["seed"]))


def paired_check(
    current: Sequence[Mapping[str, Any]], candidate: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    a = {pair_key(r): validation_f(r) for r in current}
    b = {pair_key(r): validation_f(r) for r in candidate}
    if set(a) != set(b):
        raise ValueError("candidate and current runs are not paired seed for seed")
    diffs = [b[k] - a[k] for k in sorted(a)]
    median = statistics.median(diffs)
    return {
        "pairs": len(diffs),
        "median_difference": median,
        "threshold": THRESHOLD,
        "admitted": median >= THRESHOLD,
        "share_better": sum(d > 0 for d in diffs) / len(diffs),
        "share_equal": sum(d == 0 for d in diffs) / len(diffs),
    }
