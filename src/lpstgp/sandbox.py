"""Leakage-safe data access for all modelling code (operators, GP fitness, gates, maintenance).

A ``Sandbox`` for (period, stage) holds, per instrument, exactly ``lookback_max`` warm-up bars
before the fit start followed by every bar up to (excluding) the stage horizon:

* ``Stage.FIT``      horizon = validation start: nothing from the validation or test years;
* ``Stage.VALIDATE`` horizon = test start: nothing from the test year;
* ``Stage.TEST``     sealed in WP1 (``SealedPeriodError``); WP4 adds a sealed evaluator that
  requires a frozen, hashed rule before any test bar is read.

The sandbox keeps no reference to the store, so code holding a sandbox cannot reach later rows.
Every sandbox records what it read (``access_log``) for the run record.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

import numpy as np

from lpstgp.data.store import Bars, DataStore
from lpstgp.splits import Period, Stage, shift_years

# Calendar years read before the fit start; ample for 504 bars on any calendar.
WARMUP_READ_YEARS = 3


class SealedPeriodError(PermissionError):
    """Test-period data are not accessible from modelling code."""


@dataclass(frozen=True)
class AccessRecord:
    period: str
    stage: str
    instrument: str
    read_start: date
    horizon: date
    warmup_bars: int
    bars: int
    first_date: str
    last_date: str


def _trim(bars: Bars, fit_start: date, lookback_max: int) -> Bars:
    """Keep the last ``lookback_max`` bars before ``fit_start`` and everything after it."""
    first_fit = int(np.searchsorted(bars.dates, np.datetime64(fit_start)))
    lo = max(0, first_fit - lookback_max)
    if lo == 0:
        return bars
    fields = {}
    for name in (
        "dates",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "dividend",
        "split",
        "log_return",
        "log_price",
    ):
        view = getattr(bars, name)[lo:].copy()
        view.setflags(write=False)
        fields[name] = view
    return Bars(
        instrument_id=bars.instrument_id,
        calendar=bars.calendar,
        start=bars.start,
        horizon=bars.horizon,
        meta=bars.meta,
        **fields,
    )


@dataclass(frozen=True, eq=False)
class Sandbox:
    period: Period
    stage: Stage
    horizon: date
    lookback_max: int
    bars: Mapping[str, Bars]
    access_log: tuple[AccessRecord, ...] = field(default=())

    @classmethod
    def open(
        cls,
        store: DataStore,
        period: Period,
        stage: Stage,
        instruments: Iterable[str],
        lookback_max: int,
    ) -> Sandbox:
        if stage is Stage.TEST:
            raise SealedPeriodError(
                f"{period.id}: test-period data are sealed; modelling code may only use FIT or VALIDATE"
            )
        horizon = period.horizon(stage)
        read_start = shift_years(period.fit_start, -WARMUP_READ_YEARS)
        loaded: dict[str, Bars] = {}
        log = []
        for instrument in instruments:
            bars = _trim(
                store.read(instrument, read_start, horizon), period.fit_start, lookback_max
            )
            if len(bars) and bars.dates[-1] >= np.datetime64(horizon):
                raise AssertionError("sandbox received a bar at or after its horizon")
            loaded[instrument] = bars
            warmup = int(np.count_nonzero(bars.dates < np.datetime64(period.fit_start)))
            log.append(
                AccessRecord(
                    period.id,
                    stage.value,
                    instrument,
                    read_start,
                    horizon,
                    warmup,
                    len(bars),
                    str(bars.dates[0]) if len(bars) else "",
                    str(bars.dates[-1]) if len(bars) else "",
                )
            )
        return cls(period, stage, horizon, lookback_max, MappingProxyType(loaded), tuple(log))

    def __getitem__(self, instrument: str) -> Bars:
        return self.bars[instrument]

    @property
    def instruments(self) -> tuple[str, ...]:
        return tuple(self.bars)

    @property
    def key(self) -> tuple[str, str, str, int]:
        """Identity for cache keys: never share outputs across periods, stages or horizons."""
        return (self.period.id, self.stage.value, self.horizon.isoformat(), self.lookback_max)

    def scored_mask(self, instrument: str) -> np.ndarray:
        """Bars this stage is scored on (fit years for FIT, the validation year for VALIDATE)."""
        lo, hi = self.period.scored_window(self.stage)
        dates = self.bars[instrument].dates
        return (dates >= np.datetime64(lo)) & (dates < np.datetime64(hi))
