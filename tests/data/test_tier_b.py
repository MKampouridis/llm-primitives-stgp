from datetime import date

import pandas as pd
import pytest

from lpstgp.data.tier_b import InMemoryTierBSource, SecurityRecord, SelectionRule, WRDSSource
from lpstgp.splits import walk_forward

AS_OF = date(2005, 7, 1)


def sec(
    sid, issuer, country, mcap, primary=True, common=True, listed=date(1990, 1, 1), delisted=None
):
    return SecurityRecord(sid, issuer, sid, country, mcap, primary, common, listed, delisted)


def test_largest_per_market_with_one_class_per_issuer():
    universe = [
        sec("US1", "A", "US", 300.0),
        sec("US1B", "A", "US", 250.0),  # second share class of issuer A: dropped
        sec("US2", "B", "US", 200.0),
        sec("US3", "C", "US", 100.0),
        sec("UK1", "D", "GB", 50.0),
        sec("DE1", "E", "DE", 80.0),
        sec("JP1", "F", "JP", 90.0),
    ]
    picks = SelectionRule(per_market=2).select(universe, AS_OF)
    assert picks == {"US": ["US1", "US2"], "EUROPE": ["DE1"], "UK": ["UK1"], "JAPAN_ASIA": ["JP1"]}


def test_filters_and_survivorship():
    universe = [
        sec("ADR", "A", "US", 900.0, primary=False),
        sec("PREF", "B", "US", 800.0, common=False),
        sec("LATER", "C", "US", 700.0, listed=date(2006, 1, 1)),  # not yet listed
        sec("GONE", "D", "US", 600.0, delisted=date(2004, 1, 1)),  # already delisted
        sec("DIES", "E", "US", 500.0, delisted=date(2009, 3, 1)),  # delisted later: stays selected
        sec("AU1", "F", "AU", 400.0),  # country outside the four markets
        sec("OK", "G", "US", 100.0),
    ]
    picks = SelectionRule(per_market=5).select(universe, AS_OF)
    assert picks["US"] == ["DIES", "OK"]


def test_ties_are_broken_by_security_id():
    universe = [sec("B", "X", "US", 100.0), sec("A", "Y", "US", 100.0)]
    assert SelectionRule(per_market=1).select(universe, AS_OF)["US"] == ["A"]


def test_selection_dates_by_mode():
    periods = walk_forward(date(2005, 7, 1), 3)
    assert SelectionRule(mode="once").selection_dates(periods) == [date(2005, 7, 1)]
    assert SelectionRule(mode="per_period").selection_dates(periods) == [
        date(2005, 7, 1),
        date(2006, 7, 1),
        date(2007, 7, 1),
    ]


def test_run_uses_point_in_time_snapshots():
    source = InMemoryTierBSource(
        {
            date(2005, 6, 30): [sec("US1", "A", "US", 10.0), sec("US2", "B", "US", 5.0)],
            date(2006, 6, 30): [sec("US1", "A", "US", 1.0), sec("US2", "B", "US", 5.0)],
        }
    )
    periods = walk_forward(date(2005, 7, 1), 2)
    result = SelectionRule(per_market=1, mode="per_period").run(source, periods)
    assert result[date(2005, 7, 1)]["US"] == ["US1"]
    assert result[date(2006, 7, 1)]["US"] == ["US2"]


def test_in_memory_bars_respect_horizon():
    frame = pd.DataFrame({"date": pd.bdate_range("2005-01-03", periods=10), "close": range(10)})
    source = InMemoryTierBSource({}, bars={"S": frame})
    window = source.bars("S", date(2005, 1, 4), date(2005, 1, 10))
    assert window["date"].min() >= pd.Timestamp("2005-01-04")
    assert window["date"].max() < pd.Timestamp("2005-01-10")


def test_vendor_stubs_name_their_credentials():
    with pytest.raises(NotImplementedError, match="WRDS_USERNAME"):
        WRDSSource().snapshot(AS_OF)
