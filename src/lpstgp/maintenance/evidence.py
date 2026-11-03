"""Per-operator evidence from one cycle's run records, FIT stage only (protocol_wp3 §4.1).

Inputs are the run records of one library state on one period (one run per instrument and seed,
``knockouts`` on). Nothing here reads data: the records were made through the sandbox's FIT
stage, and the validation fields of the records are never used. The rendered text names no
instrument, only asset classes.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from lpstgp.operators.contract import OperatorSpec

# Prune rule (§4.2, provisional, D-071): low usage and low contribution in this cycle and the one
# before (the last cycle of the previous period counts as the one before the first).
PRUNE_MAX_USAGE = 0.02
PRUNE_MAX_CONTRIBUTION = 0.01


def _iqr(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    q1, q3 = np.percentile(values, [25, 75])
    return float(q3 - q1)


def gp_names(specs: Sequence[OperatorSpec]) -> dict[str, tuple[str, int]]:
    """The maintained (cross-domain) operators of a library: gp name -> (name, version)."""
    return {
        s.gp_name: (s.name, s.version)
        for s in specs
        if isinstance(s, OperatorSpec) and s.domain not in ("core", "data")
    }


def operator_rows(
    records: Sequence[Mapping[str, Any]], operators: Mapping[str, tuple[str, int]]
) -> dict[str, dict[str, Any]]:
    """Evidence per operator key (name@version); ``operators`` maps gp name -> (name, version)."""
    hall = [(r, h) for r in records for h in r["hall_of_fame"]]
    rows = {}
    for gpn, (name, version) in operators.items():
        uses = [gpn in h["entry"] or gpn in h["exit"] for _, h in hall]
        survival = []
        for r in records:
            gens = r["generations"]
            survival.append(sum(gpn in g.get("best_usage", ()) for g in gens) / len(gens))
        deltas, by_instrument, by_segment = [], defaultdict(list), defaultdict(list)
        for r in records:
            for ko in r.get("knockouts", []):
                cell = ko["operators"].get(gpn)
                if cell is None:
                    continue
                deltas.append(cell["delta_f"])
                for inst, segs in cell["delta_segment_sharpe"].items():
                    by_instrument[inst].append(cell["delta_f"])
                    for k, d in enumerate(segs):
                        by_segment[(inst, k)].append(d)
        ms = []
        for r in records:
            o = r.get("operator_seconds", {}).get(gpn)
            if o and o["calls"]:
                ms.append(1000 * o["seconds"] / o["calls"])
        rows[f"{name}@{version}"] = {
            "name": name,
            "version": version,
            "gp_name": gpn,
            "usage": sum(uses) / len(uses) if uses else 0.0,
            "rules_using": int(sum(uses)),
            "survival": statistics.fmean(survival) if survival else 0.0,
            "contribution": statistics.fmean(deltas) if deltas else None,
            "stability_instruments_iqr": _iqr(
                [statistics.fmean(v) for v in by_instrument.values()]
            ),
            "stability_segments_iqr": _iqr([statistics.fmean(v) for v in by_segment.values()]),
            "cost_ms": statistics.median(ms) if ms else None,
        }
    return rows


def low(row: Mapping[str, Any]) -> bool:
    contribution = row.get("contribution")
    return row["usage"] <= PRUNE_MAX_USAGE and (
        contribution is None or contribution <= PRUNE_MAX_CONTRIBUTION
    )


def prunable(
    key: str, current: Mapping[str, Mapping], previous: Mapping[str, Mapping] | None
) -> bool:
    """The gate's prune rule: low in this cycle and in the previous one (same key)."""
    return (
        key in current
        and previous is not None
        and key in previous
        and low(current[key])
        and low(previous[key])
    )


def elite_rules(
    records: Sequence[Mapping[str, Any]], asset_class: Mapping[str, str], n: int = 20
) -> list[dict[str, Any]]:
    """The best rank-0 hall-of-fame rule of each run, top ``n`` by FIT fitness, anonymised."""
    best = []
    for r in records:
        if not r["hall_of_fame"]:
            continue
        h = r["hall_of_fame"][0]
        (inst,) = r["instruments"]
        best.append(
            {
                "asset_class": asset_class[inst],
                "fit_fitness": h["fit"]["fitness"],
                "entry": h["entry_str"],
                "exit": h["exit_str"],
            }
        )
    best.sort(key=lambda b: (-b["fit_fitness"], b["entry"], b["exit"]))
    return best[:n]


def summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Library-level FIT figures of the cycle (for the brief and the lineage)."""
    fits = [r["hall_of_fame"][0]["fit"]["fitness"] for r in records if r["hall_of_fame"]]
    no_trade = [
        all(c.get("no_trade", False) for c in r["hall_of_fame"][0]["fit"]["instruments"].values())
        for r in records
        if r["hall_of_fame"]
    ]
    return {
        "runs": len(records),
        "median_fit_fitness": statistics.median(fits) if fits else None,
        "no_trade_share": sum(no_trade) / len(no_trade) if no_trade else None,
    }


def render_table(rows: Mapping[str, Mapping[str, Any]], history: Mapping[str, Sequence]) -> str:
    """Markdown evidence table; ``history`` gives each key's rows from earlier cycles."""

    def f(x, d=3):
        return "–" if x is None else f"{x:.{d}f}"

    lines = [
        "| operator | GP node | usage | survival | contribution | stab. (instr. IQR) | "
        "stab. (segment IQR) | ms/call | earlier usage / contribution |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key in sorted(rows):
        r = rows[key]
        past = "; ".join(
            f"{f(h['usage'], 2)} / {f(h.get('contribution'))}" for h in history.get(key, [])
        )
        lines.append(
            f"| `{key}` | `{r['gp_name']}` | {f(r['usage'], 3)} | {f(r['survival'], 3)} | "
            f"{f(r['contribution'])} | {f(r['stability_instruments_iqr'])} | "
            f"{f(r['stability_segments_iqr'])} | {f(r['cost_ms'], 1)} | {past or '–'} |"
        )
    return "\n".join(lines)
