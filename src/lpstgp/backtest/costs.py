"""Transaction costs: per-asset one-way costs (buy/sell may differ) and a global multiplier.

Base costs come from a documented broker-spread model (D-028); contemporaneous spreads can be
passed as a per-bar array instead of a constant. The multiplier implements the sensitivity sweep
(0.5x, 1x, 2x, 3x).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

BPS = 1e-4


@dataclass(frozen=True)
class CostModel:
    buy_bps: float | np.ndarray  # cost of a unit increase in the position (one way)
    sell_bps: float | np.ndarray  # cost of a unit decrease
    multiplier: float = 1.0

    def rates(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Per-bar buy and sell cost rates (fractions of notional) for ``n`` bars."""
        buy = (
            np.broadcast_to(np.asarray(self.buy_bps, dtype=np.float64), (n,))
            * BPS
            * self.multiplier
        )
        sell = (
            np.broadcast_to(np.asarray(self.sell_bps, dtype=np.float64), (n,))
            * BPS
            * self.multiplier
        )
        return buy, sell

    def scaled(self, multiplier: float) -> CostModel:
        return CostModel(self.buy_bps, self.sell_bps, multiplier)


def from_meta(meta: Mapping[str, Any], multiplier: float = 1.0) -> CostModel:
    """Symmetric cost from an instrument's metadata (``cost_bps``; Tier B may add buy/sell)."""
    base = float(meta.get("cost_bps", 0.0))
    return CostModel(
        float(meta.get("buy_bps", base)), float(meta.get("sell_bps", base)), multiplier
    )
