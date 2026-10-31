"""Arm 1: per instrument, the whole strategy with the best validation fitness (D-037).

Each frozen strategy's entry/exit pair is scored with the same fitness as the GP
(``fitness.market_part``, no size term) on the FIT and VALIDATE sandboxes; the selected strategy
maximises validation fitness, the score STGP's final selection uses. Ties go to the lower id.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lpstgp.backtest.costs import CostModel
from lpstgp.gp.fitness import FitnessConfig, market_part, prepare
from lpstgp.sandbox import Sandbox
from lpstgp.strategies.adapters import Frozen


def scores(
    frozen: Sequence[Frozen], box: Sandbox, costs: Mapping[str, CostModel], cfg: FitnessConfig
) -> dict[str, dict[str, dict]]:
    """``{instrument: {sid: {"fitness": F, **components}}}`` on the sandbox's scored window."""
    window = box.period.scored_window(box.stage)
    out: dict[str, dict[str, dict]] = {}
    for name in box.instruments:
        bars = box[name]
        data = prepare(
            bars.dates, bars.log_return, bars.calendar, window, costs[name], cfg.segment_months
        )
        out[name] = {}
        for f in frozen:
            entry, exit_ = f.strategy.run(bars.log_price, bars.log_return)
            value, parts = market_part(entry, exit_, data, cfg)
            out[name][f.sid] = {"fitness": value, **parts}
    return out


def select(
    frozen: Sequence[Frozen],
    fit_box: Sandbox,
    val_box: Sandbox,
    costs: Mapping[str, CostModel],
    cfg: FitnessConfig,
) -> dict[str, dict]:
    fit, val = scores(frozen, fit_box, costs, cfg), scores(frozen, val_box, costs, cfg)
    chosen = {}
    for name in val_box.instruments:
        ranked = sorted(val[name], key=lambda sid: (-val[name][sid]["fitness"], sid))
        chosen[name] = {
            "selected": ranked[0],
            "validation": {sid: val[name][sid]["fitness"] for sid in ranked},
            "fit": {sid: fit[name][sid]["fitness"] for sid in ranked},
        }
    return chosen
