"""Leakage-safe data access for all modelling code (operators, GP fitness, gates, maintenance).

A ``Sandbox`` for (period, stage) holds, per instrument, exactly ``lookback_max`` warm-up bars
before the fit start followed by every bar up to (excluding) the stage horizon:

* ``Stage.FIT``      horizon = validation start: nothing from the validation or test years;
* ``Stage.VALIDATE`` horizon = test start: nothing from the test year;
* ``Stage.TEST``     sealed (``SealedPeriodError``). The only way in is ``open_pilot_test``: a
  pilot period (D-034) whose test year ends within the store's data cap, after a committed
  freeze manifest exists (``lpstgp.freeze``). WP4's entry is ``open_frozen_test``: a period
  listed as a test period in a committed freeze manifest's context (P01..P18, or PC on its own).

A horizon past the store's ``max_horizon`` is refused before anything is read. The sandbox keeps
no reference to the store, so code holding a sandbox cannot reach later rows. Every sandbox
records what it read (``access_log``) for the run record.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

import numpy as np

from lpstgp.data.store import Bars, DataStore
from lpstgp.freeze import FreezeManifest
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
        return cls._open(store, period, stage, instruments, lookback_max)

    @classmethod
    def open_pilot_test(
        cls,
        store: DataStore,
        period: Period,
        instruments: Iterable[str],
        lookback_max: int,
        *,
        pilot_periods: Collection[Period],
        manifest: FreezeManifest,
    ) -> Sandbox:
        """TEST stage of a pilot period, for evaluating rules frozen in a committed manifest.
        Only the pilots PL1 and PL2 (their test years are spent, D-060); never a WP4 period,
        whatever ``pilot_periods`` the caller passes (D-087)."""
        if period not in pilot_periods or not period.id.startswith("PL"):
            raise SealedPeriodError(f"{period.id}: only pilot periods have an open test stage")
        if store.max_horizon is None or period.test_end > store.max_horizon:
            raise SealedPeriodError(f"{period.id}: test year lies beyond the store's data cap")
        if not isinstance(manifest, FreezeManifest) or not manifest.verified:
            raise SealedPeriodError(
                f"{period.id}: a committed freeze manifest (FreezeManifest.load_committed) "
                "listing the frozen rules is required"
            )
        return cls._open(store, period, Stage.TEST, instruments, lookback_max)

    @classmethod
    def open_frozen_test(
        cls,
        store: DataStore,
        period: Period,
        instruments: Iterable[str],
        lookback_max: int,
        *,
        test_periods: Collection[Period],
        manifest: FreezeManifest,
    ) -> Sandbox:
        """TEST stage of a WP4 period, for evaluating rules frozen in a committed manifest that
        names this period among its test periods (D-079, D-086). The pilots stay on
        ``open_pilot_test``; their test years are spent."""
        if not isinstance(manifest, FreezeManifest) or not manifest.verified:
            raise SealedPeriodError(
                f"{period.id}: a committed freeze manifest (FreezeManifest.load_committed) "
                "listing the frozen rules is required"
            )
        named = manifest.context.get("test_periods")
        if period not in test_periods or named != sorted(p.id for p in test_periods):
            raise SealedPeriodError(f"{period.id}: not a test period of the committed manifest")
        if period.id.startswith("PL") or period.id == "DEV":
            raise SealedPeriodError(f"{period.id}: no WP4 test read for this period")
        if store.max_horizon is None or period.test_end > store.max_horizon:
            raise SealedPeriodError(f"{period.id}: test year lies beyond the store's data cap")
        claim = manifest.path.parent / "test_claim.json"
        try:
            claimed = json.loads(claim.read_text(encoding="utf-8")).get("manifest_commit")
        except (OSError, ValueError):
            claimed = None
        if claimed != manifest.commit:
            raise SealedPeriodError(
                f"{period.id}: the test read must be claimed for this manifest first "
                "(lpstgp.freeze.claim_test_read; D-087)"
            )
        return cls._open(store, period, Stage.TEST, instruments, lookback_max)

    @classmethod
    def _open(
        cls,
        store: DataStore,
        period: Period,
        stage: Stage,
        instruments: Iterable[str],
        lookback_max: int,
    ) -> Sandbox:
        named = getattr(store, "periods", None)
        if named is not None and named.get(period.id) != period:
            raise SealedPeriodError(
                f"{period.id}: not the settings' period of that name (dates differ); a sandbox "
                "opens only a named period (D-087)"
            )
        allowed = getattr(store, "allowed_periods", None)
        if allowed is not None and period.id not in allowed:
            raise SealedPeriodError(
                f"{period.id}: not among the periods this stage of the study may open "
                f"({', '.join(sorted(allowed))}; settings [leakage] allowed_periods)"
            )
        horizon = period.horizon(stage)
        if store.max_horizon is not None and horizon > store.max_horizon:
            raise SealedPeriodError(
                f"{period.id} {stage.value}: horizon {horizon} is past the data cap {store.max_horizon}"
            )
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
