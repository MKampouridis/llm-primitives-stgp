"""Calibration rules of protocol §6, applied to run records (training data only).

* ``convergence_generation``: the first generation whose best fit fitness reaches 99% of the
  run's total rise (regime-fusion-gp's rule).
* ``choose_candidate``: among equal-budget candidates, the cheapest whose median validation
  fitness is within ``tolerance`` of the best; its generations are the median convergence
  generation rounded up to 10.
* ``budget_unit``: unique evaluations if the arms' median unique shares differ by more than 2x.
* ``lambda_check``: whether too many final rules never trade on validation, or trade too much.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def convergence_generation(generations: Sequence[Mapping[str, Any]], share: float = 0.99) -> int:
    best = [g["best"] for g in generations]
    start, end = best[0], max(best)
    if end <= start:
        return int(generations[0]["gen"])
    target = start + share * (end - start)
    return next(int(g["gen"]) for g, b in zip(generations, best, strict=True) if b >= target)


def selected_validation(record: Mapping[str, Any]) -> float:
    return float(record["hall_of_fame"][record["selected"]]["validation"]["fitness"])


def choose_candidate(
    records: Iterable[Mapping[str, Any]], tolerance: float = 0.05
) -> dict[str, Any]:
    groups: dict[tuple[int, int], dict[str, list]] = defaultdict(lambda: {"val": [], "conv": []})
    for record in records:
        key = (record["config"]["population"], record["config"]["tournament"])
        groups[key]["val"].append(selected_validation(record))
        groups[key]["conv"].append(convergence_generation(record["generations"]))
    table = []
    for (population, tournament), g in sorted(groups.items()):
        generations = max(10, math.ceil(statistics.median(g["conv"]) / 10) * 10)
        table.append(
            {
                "population": population,
                "tournament": tournament,
                "runs": len(g["val"]),
                "median_validation": statistics.median(g["val"]),
                "median_convergence": statistics.median(g["conv"]),
                "generations": generations,
                "requested_evaluations": population * (generations + 1),
            }
        )
    best = max(row["median_validation"] for row in table)
    eligible = [row for row in table if row["median_validation"] >= best - tolerance]
    chosen = min(eligible, key=lambda r: (r["requested_evaluations"], -r["median_validation"]))
    return {**chosen, "best_median_validation": best, "tolerance": tolerance, "table": table}


def budget_unit(records: Iterable[Mapping[str, Any]], ratio: float = 2.0) -> dict[str, Any]:
    shares: dict[str, list[float]] = defaultdict(list)
    for record in records:
        b = record["budget"]
        shares[record["library"]["name"]].append(
            b["unique_evaluations"] / b["requested_evaluations"]
        )
    medians = {arm: statistics.median(v) for arm, v in sorted(shares.items())}
    spread = max(medians.values()) / min(medians.values())
    return {
        "unit": "unique" if spread > ratio else "requested",
        "median_unique_share": medians,
        "spread": spread,
    }


def lambda_check(
    records: Iterable[Mapping[str, Any]], max_no_trade: float = 0.25, max_turnover: float = 50.0
) -> dict[str, Any]:
    no_trade, turnovers = [], []
    for record in records:
        val = record["hall_of_fame"][record["selected"]]["validation"]
        for comps in val["instruments"].values():
            no_trade.append(bool(comps.get("no_trade")))
            if not comps.get("no_trade"):
                turnovers.append(comps["median_turnover"])
    share = sum(no_trade) / max(len(no_trade), 1)
    median_turnover = statistics.median(turnovers) if turnovers else 0.0
    return {
        "no_trade_share": share,
        "median_turnover": median_turnover,
        "raise_lambda_turnover": share > max_no_trade or median_turnover > max_turnover,
    }
