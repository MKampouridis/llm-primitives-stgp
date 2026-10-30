"""Rolling walk-forward periods: train = fit (2 y) + validation (1 y); test = the next year.

All interval ends are exclusive. ``Period.horizon(stage)`` is the first date that a stage may
*not* see: fitting sees nothing from the validation start on, validation nothing from the test
start on. Test access is sealed in ``sandbox.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

import numpy as np


class Stage(Enum):
    FIT = "fit"
    VALIDATE = "validate"
    TEST = "test"


@dataclass(frozen=True, order=True)
class Period:
    id: str
    fit_start: date
    val_start: date
    test_start: date
    test_end: date

    @property
    def fit_end(self) -> date:
        return self.val_start

    @property
    def val_end(self) -> date:
        return self.test_start

    def horizon(self, stage: Stage) -> date:
        """Exclusive upper bound on the dates visible to ``stage``."""
        return {
            Stage.FIT: self.val_start,
            Stage.VALIDATE: self.test_start,
            Stage.TEST: self.test_end,
        }[stage]

    def scored_window(self, stage: Stage) -> tuple[date, date]:
        """The dates a stage is scored on: fit, validation or test year(s)."""
        return {
            Stage.FIT: (self.fit_start, self.val_start),
            Stage.VALIDATE: (self.val_start, self.test_start),
            Stage.TEST: (self.test_start, self.test_end),
        }[stage]


def shift_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February
        return day.replace(year=day.year + years, day=28)


def walk_forward(
    first_fit_start: date,
    n_periods: int,
    fit_years: int = 2,
    validation_years: int = 1,
    test_years: int = 1,
    step_years: int = 1,
) -> tuple[Period, ...]:
    periods = []
    for k in range(n_periods):
        fit_start = shift_years(first_fit_start, k * step_years)
        val_start = shift_years(fit_start, fit_years)
        test_start = shift_years(val_start, validation_years)
        test_end = shift_years(test_start, test_years)
        periods.append(Period(f"P{k + 1:02d}", fit_start, val_start, test_start, test_end))
    return tuple(periods)


def periods_from_settings(settings: Mapping[str, Any]) -> tuple[Period, ...]:
    cfg = settings["splits"]
    return walk_forward(
        cfg["first_fit_start"],
        cfg["n_periods"],
        cfg["fit_years"],
        cfg["validation_years"],
        cfg["test_years"],
        cfg["step_years"],
    )


def is_eligible(
    valid_dates: np.ndarray,
    expected_sessions: np.ndarray,
    period: Period,
    lookback_max: int,
    min_coverage: float,
) -> bool:
    """Availability-only eligibility of one instrument for one period.

    Requires ``lookback_max`` valid bars before the fit start (warm-up for any rule) and at least
    ``min_coverage`` of the expected sessions in ``[fit_start, test_end)`` to be present.
    """
    dates = np.asarray(valid_dates, dtype="datetime64[D]")
    expected = np.asarray(expected_sessions, dtype="datetime64[D]")
    lo, hi = np.datetime64(period.fit_start), np.datetime64(period.test_end)
    if np.count_nonzero(dates < lo) < lookback_max:
        return False
    n_expected = np.count_nonzero((expected >= lo) & (expected < hi))
    if n_expected == 0:
        return False
    in_window = dates[(dates >= lo) & (dates < hi)]
    present = np.count_nonzero(np.isin(in_window, expected))
    return present / n_expected >= min_coverage
