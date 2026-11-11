"""Synthetic daily bars with a planted trading signal (tier S; GP development E5, D-101).

No market data are read or written here. A *world* is a pool of instruments whose returns are
noise with a known edge added:

    r_t = sigma_t * (kappa * s_{t-lag} + z_t),        kappa = planted Sharpe / sqrt(bars a year)

* ``z_t`` is the noise: unit-variance Student-t shocks, correlated across the pool through one
  common factor (``rho``), with GARCH(1,1) volatility ``sigma_t`` per instrument.
* ``s_t`` in {+1, -1} is the planted position, decided at bar t's close by ``signal`` from the
  instrument's own bars up to t (unknown while the signal is unknown: no drift). The drift is
  proportional to ``sigma_t``, so a rule that holds ``s`` earns an annualised Sharpe ratio of
  about ``sharpe`` before costs at any volatility, under the backtest's execution lag.

Because ``s`` depends on the prices it then moves, the bars are generated one at a time. Each
bar's shocks are drawn together, so a longer simulation repeats a shorter one exactly (prefix
invariance), and bar t never depends on a later draw. The log prices and returns handed to
``signal`` are the ones the data store will compute from the stored closes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lpstgp.data import schema

TIER = "S"
# Decides the planted position at the last bar of a window: 1 (long), 0 (short) or NaN (unknown).
Signal = Callable[[np.ndarray, np.ndarray], float]


@dataclass(frozen=True)
class NoiseModel:
    annual_vol: float = 0.18  # unconditional volatility of an instrument
    alpha: float = 0.08  # GARCH(1,1): weight of the last squared shock
    beta: float = 0.90  # GARCH(1,1): weight of the last variance
    rho: float = 0.5  # correlation of the shocks across the pool (one common factor)
    dof: float = 6.0  # Student-t degrees of freedom of the shocks (fat tails)
    periods_per_year: int = 252

    def __post_init__(self) -> None:
        if not (self.alpha >= 0 and self.beta >= 0 and self.alpha + self.beta < 1):
            raise ValueError("GARCH weights must be non-negative and sum to less than 1")
        if not (0 <= self.rho < 1 and self.dof > 2):
            raise ValueError("rho must be in [0, 1) and dof above 2")


NOISE = NoiseModel()  # E5's noise (D-101)


def world_seed(world: str) -> int:
    """Seed of a world's shocks: its name only, so every process generates the same world."""
    return int.from_bytes(hashlib.sha256(f"planted|{world}".encode()).digest()[:8], "big")


def simulate(
    n_bars: int,
    n_instruments: int,
    seed: int,
    sharpe: float = 0.0,
    signal: Signal | None = None,
    lookback: int = 0,
    lag: int = 2,
    noise: NoiseModel = NOISE,
    start_price: float = 100.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Closes and planted positions, both (bars x instruments). ``signal`` sees the last
    ``lookback`` bars (log prices, log returns) ending at the bar being decided; without it, or
    with ``sharpe = 0``, the world is pure noise and the planted positions are all unknown."""
    rng = np.random.default_rng(seed)
    k = n_instruments
    planted = sharpe != 0.0 and signal is not None
    if planted and lookback < 1:
        raise ValueError("a planted signal needs its lookback")
    kappa = sharpe / np.sqrt(noise.periods_per_year)
    unit = np.sqrt((noise.dof - 2.0) / noise.dof)  # scales a Student-t draw to unit variance
    var0 = noise.annual_vol**2 / noise.periods_per_year
    omega = var0 * (1.0 - noise.alpha - noise.beta)
    close = np.empty((n_bars, k))
    log_price = np.empty((n_bars, k))
    log_return = np.full((n_bars, k), np.nan)
    position = np.full((n_bars, k), np.nan)
    var = np.full(k, var0)
    z_prev = np.zeros(k)
    previous = np.full(k, np.log(start_price))
    for t in range(n_bars):
        draw = rng.standard_t(noise.dof, size=k + 1) * unit  # one bar's shocks, drawn together
        z = np.sqrt(noise.rho) * draw[0] + np.sqrt(1.0 - noise.rho) * draw[1:]
        if t > 0:
            var = omega + (noise.alpha * z_prev**2 + noise.beta) * var
        drift = np.zeros(k)
        if planted and t >= lag:
            drift = kappa * np.nan_to_num(position[t - lag])
        close[t] = np.exp(previous + np.sqrt(var) * (drift + z))
        log_price[t] = np.log(close[t])  # as the store computes it from the stored close
        if t > 0:
            log_return[t] = log_price[t] - log_price[t - 1]
        previous, z_prev = log_price[t], z
        if planted and t + 1 >= lookback:
            lo = t + 1 - lookback
            for i in range(k):
                value = signal(log_price[lo : t + 1, i], log_return[lo : t + 1, i])
                if np.isfinite(value):
                    position[t, i] = 1.0 if value == 1.0 else -1.0
    return close, position


def write_world(
    tier_dir: Path,
    names: Sequence[str],
    dates: np.ndarray,
    close: np.ndarray,
    planted: Mapping[str, Any],
    cost_bps: float,
    noise: NoiseModel = NOISE,
) -> list[Path]:
    """One processed file per instrument, in the canonical schema (close only). ``planted``
    (world, rule, Sharpe, the rule's trees) goes into the metadata, which only reports read."""
    out = []
    for i, name in enumerate(names):
        bars, flags = schema.normalise(pd.DataFrame({"date": dates, "close": close[:, i]}))
        if len(flags):
            raise ValueError(f"{name}: the simulated closes are not valid bars")
        meta = {
            "schema_version": schema.SCHEMA_VERSION,
            "instrument_id": name,
            "tier": TIER,
            "asset_class": "synthetic",
            "calendar": "business",
            "source": "lpstgp.data.synthetic",
            "source_symbol": name,
            "close_only": True,
            "vendor_split_adjusted": False,
            "raw_files": [],
            "cost_bps": cost_bps,
            "planted": dict(planted),
            "noise": asdict(noise),
        }
        path = Path(tier_dir) / "processed" / f"{name}.parquet"
        schema.write_parquet(bars, meta, path)
        out.append(path)
    return out
