"""Gate 3 of protocol_wp3 §4.3: the paired-seed check on the validation year.

The candidate library's cycle runs and the current library's runs share their seeds (instrument,
period, run). Each run's final rule (selected on validation, as in every arm) has a validation
fitness F in its record. The candidate is rejected only when a one-sided Wilcoxon signed-rank
test of the paired differences (candidate - current) finds it worse at level ``ALPHA`` (D-072). A
guard against harm, not a search for improvement (D-066). The LLM is told only whether its patch
was admitted, never the figure (D-071).

D-072 replaced the first rule (reject when the median difference is below -0.05): in the M4 dry
run, the median difference of two replicate batches of the same library had a standard deviation
of about 0.13 at 66 pairs, so that rule rejected roughly a third of harmless patches.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from scipy.stats import wilcoxon

ALPHA = 0.05  # provisional (D-072)


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
    p_harm = (
        1.0 if all(d == 0 for d in diffs) else float(wilcoxon(diffs, alternative="less").pvalue)
    )
    return {
        "pairs": len(diffs),
        "median_difference": median,
        "test": "wilcoxon signed-rank, one-sided (candidate worse)",
        "p_harm": p_harm,
        "alpha": ALPHA,
        "admitted": p_harm >= ALPHA,
        "share_better": sum(d > 0 for d in diffs) / len(diffs),
        "share_equal": sum(d == 0 for d in diffs) / len(diffs),
    }
