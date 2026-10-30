from datetime import date

import numpy as np
import pandas as pd

from lpstgp.config import load_settings
from lpstgp.data import quality
from lpstgp.splits import periods_from_settings


def test_expected_sessions_variants():
    seven = quality.expected_sessions("7day", "", date(2020, 12, 24), date(2020, 12, 27))
    assert len(seven) == 4
    weekdays = quality.expected_sessions("business", "", date(2020, 12, 24), date(2020, 12, 28))
    assert len(weekdays) == 3  # Thu, Fri, Mon
    nyse = quality.expected_sessions("business", "XNYS", date(2020, 12, 24), date(2020, 12, 28))
    assert np.datetime64("2020-12-25") not in nyse and len(nyse) == 2


def test_longest_gap_and_stale_runs():
    expected = np.arange(np.datetime64("2020-01-01"), np.datetime64("2020-01-11"))
    present = np.delete(expected, [2, 3, 4, 7])
    assert quality.longest_gap(present, expected) == 3
    close = np.array([1, 1, 1, 1, 1, 2, 3, 3, 3, 3, 3, 3, np.nan, 4], dtype=float)
    assert quality.stale_runs(close, 5) == 2
    assert quality.stale_runs(close, 7) == 0


def test_jump_flags_use_trailing_scale():
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, 400)
    r[300] = 0.5
    close = np.exp(np.cumsum(r))
    assert quality.jump_flags(close, 8.0, 63) == 1
    # the flag at bar 300 is unaffected by anything after it
    assert quality.jump_flags(close[:301], 8.0, 63) == 1


def test_assess_counts_and_eligibility():
    settings = load_settings()
    periods = periods_from_settings(settings)
    dates = pd.bdate_range("2002-01-01", "2026-06-30")
    rng = np.random.default_rng(2)
    frame = pd.DataFrame(
        {
            "date": dates.to_numpy().astype("datetime64[D]"),
            "close": np.exp(np.cumsum(rng.normal(0, 0.01, len(dates)))),
            "volume": np.nan,
        }
    )
    frame.loc[10, "close"] = np.nan
    flags = pd.DataFrame({"date": [dates[10]], "flag": ["invalid_close"]})
    meta = {"calendar": "business", "qa_calendar": "", "close_only": True}
    result = quality.assess(frame, flags, meta, periods, settings)
    assert result["bars"] == len(dates) - 1
    assert result["missing"] == 1 and result["longest_gap"] == 1
    assert result["volume_share"] == 0.0
    assert result["eligible"] == [p.id for p in periods]
