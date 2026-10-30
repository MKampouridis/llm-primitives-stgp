"""Horizon-enforcing read access to processed bars: the only path from disk to modelling code.

``DataStore.read(instrument, start, horizon)`` returns rows with ``start <= date < horizon`` only.
Files have one row group per calendar month, so with month-aligned horizons (all walk-forward
horizons fall on the 1st of a month) row groups at or after the horizon are pruned by their
statistics and never read. The returned arrays are owned, read-only copies: nothing reachable
from a ``Bars`` object refers to later rows.

Adjustment is causal: the total log return of a bar uses only that bar's events (dividend, split)
and the previous valid close; the log-price path adds the cumulative event adjustment *since the
read start* to the raw log close, so later events never rewrite earlier values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from lpstgp.data import schema


def _readonly(values: np.ndarray, dtype: str | None = None) -> np.ndarray:
    out = np.array(values, dtype=dtype, copy=True)
    out.setflags(write=False)
    return out


@dataclass(frozen=True, eq=False)
class Bars:
    instrument_id: str
    calendar: str
    start: date
    horizon: date
    dates: np.ndarray  # datetime64[D]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray  # raw close; NaN on invalid bars
    volume: np.ndarray
    dividend: np.ndarray
    split: np.ndarray
    log_return: (
        np.ndarray
    )  # point-in-time total log return; NaN on the first valid bar and invalid bars
    log_price: (
        np.ndarray
    )  # log close + cumulative event adjustment since `start`; NaN on invalid bars
    meta: Mapping[str, Any]

    def __len__(self) -> int:
        return len(self.dates)


def causal_returns(
    close: np.ndarray, dividend: np.ndarray, split: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Total log returns and the event-adjusted log-price path, both strictly causal.

    Events on invalid bars are carried to the next valid bar. With no events the path equals
    ``log(close)`` exactly.
    """
    n = len(close)
    log_return = np.full(n, np.nan)
    log_price = np.full(n, np.nan)
    adjustment = 0.0
    pending_cash = 0.0  # dividends per share since the last valid bar
    pending_split = 1.0  # split ratio since the last valid bar
    previous = -1
    for i in range(n):
        pending_cash += dividend[i]
        pending_split *= split[i]
        c = close[i]
        if not np.isfinite(c):
            continue
        event = 0.0
        if pending_split != 1.0:
            event += np.log(pending_split)
        if pending_cash != 0.0:
            event += np.log1p(pending_cash / c)
        pending_cash, pending_split = 0.0, 1.0
        log_c = np.log(c)
        if previous >= 0:
            adjustment += event
            log_return[i] = log_c - np.log(close[previous]) + event
        log_price[i] = log_c + adjustment if adjustment != 0.0 else log_c
        previous = i
    return log_return, log_price


class DataStore:
    """Read-only access to one tier's processed files."""

    def __init__(self, tier_dir: Path) -> None:
        self._processed = Path(tier_dir) / "processed"

    def instruments(self) -> list[str]:
        return sorted(
            p.stem
            for p in self._processed.glob("*.parquet")
            if not p.name.endswith(".flags.parquet")
        )

    def path(self, instrument_id: str) -> Path:
        path = self._processed / f"{instrument_id}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"no processed data for {instrument_id} in {self._processed}")
        return path

    def meta(self, instrument_id: str) -> Mapping[str, Any]:
        return MappingProxyType(schema.read_meta(self.path(instrument_id)))

    def read(self, instrument_id: str, start: date, horizon: date) -> Bars:
        if not start < horizon:
            raise ValueError(f"start {start} must precede horizon {horizon}")
        path = self.path(instrument_id)
        table = pq.read_table(path, filters=[("date", ">=", start), ("date", "<", horizon)])
        dates = _readonly(table["date"].to_numpy(), "datetime64[D]")
        columns = {
            name: _readonly(table[name].to_numpy(zero_copy_only=False), "float64")
            for name in schema.COLUMNS[1:]
        }
        del table
        if len(dates) and not (
            dates[0] >= np.datetime64(start) and dates[-1] < np.datetime64(horizon)
        ):
            raise AssertionError("store returned rows outside [start, horizon)")
        log_return, log_price = causal_returns(
            columns["close"], columns["dividend"], columns["split"]
        )
        meta = schema.read_meta(path)
        return Bars(
            instrument_id=instrument_id,
            calendar=meta["calendar"],
            start=start,
            horizon=horizon,
            dates=dates,
            log_return=_readonly(log_return),
            log_price=_readonly(log_price),
            meta=MappingProxyType(meta),
            **columns,
        )
