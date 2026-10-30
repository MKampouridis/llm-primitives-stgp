from datetime import date
from itertools import pairwise

import numpy as np
import pytest

from lpstgp.config import load_settings
from lpstgp.splits import Stage, is_eligible, periods_from_settings, shift_years, walk_forward


def test_default_schedule():
    periods = periods_from_settings(load_settings())
    assert len(periods) == 18
    p1, p18 = periods[0], periods[-1]
    assert (p1.fit_start, p1.val_start, p1.test_start, p1.test_end) == (
        date(2005, 7, 1),
        date(2007, 7, 1),
        date(2008, 7, 1),
        date(2009, 7, 1),
    )
    assert (p18.test_start, p18.test_end) == (date(2025, 7, 1), date(2026, 7, 1))
    assert [p.id for p in periods[:2]] == ["P01", "P02"]


def test_periods_roll_by_one_year_and_are_contiguous():
    periods = walk_forward(date(2005, 7, 1), 5)
    for a, b in pairwise(periods):
        assert b.fit_start == shift_years(a.fit_start, 1)
        assert b.val_start == a.test_start  # P(k)'s test year is P(k+1)'s validation year
    for p in periods:
        assert p.fit_start < p.val_start < p.test_start < p.test_end


def test_horizons_and_scored_windows():
    p = walk_forward(date(2005, 7, 1), 1)[0]
    assert p.horizon(Stage.FIT) == p.val_start
    assert p.horizon(Stage.VALIDATE) == p.test_start
    assert p.scored_window(Stage.FIT) == (p.fit_start, p.val_start)
    assert p.scored_window(Stage.VALIDATE) == (p.val_start, p.test_start)


def test_shift_years_handles_leap_day():
    assert shift_years(date(2008, 2, 29), 1) == date(2009, 2, 28)


@pytest.fixture
def period():
    return walk_forward(date(2005, 7, 1), 1)[0]


def _weekdays(lo, hi):
    days = np.arange(np.datetime64(lo), np.datetime64(hi))
    return days[np.is_busday(days)]


def test_eligibility_requires_warmup(period):
    expected = _weekdays("2000-01-01", "2010-01-01")
    full = expected
    late = expected[expected >= np.datetime64("2005-01-01")]
    assert is_eligible(full, expected, period, 504, 0.95)
    assert not is_eligible(late, expected, period, 504, 0.95)


def test_eligibility_requires_coverage(period):
    expected = _weekdays("2000-01-01", "2010-01-01")
    sparse = expected[::2]
    assert not is_eligible(sparse, expected, period, 504, 0.95)
