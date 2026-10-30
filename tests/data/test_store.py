from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.data import schema
from lpstgp.data.store import DataStore, causal_returns

META = {
    "schema_version": 1,
    "instrument_id": "TST",
    "tier": "A",
    "asset_class": "bond",
    "calendar": "business",
    "source": "unit",
    "source_symbol": "T",
    "close_only": True,
    "vendor_split_adjusted": False,
    "raw_files": [],
}


def _bars(n=800, seed=3):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2004-01-01", periods=n)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    dividend = np.where(np.arange(n) % 63 == 20, 0.3, 0.0)
    frame = pd.DataFrame({"date": dates, "close": close, "dividend": dividend})
    frame.loc[150, "close"] = np.nan
    bars, _ = schema.normalise(frame)
    return bars


@pytest.fixture
def store(tmp_path):
    schema.write_parquet(_bars(), META, tmp_path / "processed" / "TST.parquet")
    return DataStore(tmp_path)


def test_read_returns_only_rows_inside_window(store):
    bars = store.read("TST", date(2004, 3, 1), date(2005, 7, 1))
    assert bars.dates.min() >= np.datetime64("2004-03-01")
    assert bars.dates.max() < np.datetime64("2005-07-01")


def test_arrays_are_read_only_copies(store):
    bars = store.read("TST", date(2004, 1, 1), date(2005, 7, 1))
    for name in ("dates", "close", "log_return", "log_price", "dividend"):
        array = getattr(bars, name)
        assert not array.flags.writeable
        assert array.base is None or not array.base.flags.writeable
        with pytest.raises(ValueError):
            array[0] = 0


def test_rows_after_horizon_cannot_influence_a_read(tmp_path):
    """Canary: poisoning everything at or after the horizon leaves the read unchanged."""
    clean = _bars()
    poisoned = clean.copy()
    late = poisoned["date"] >= pd.Timestamp("2005-07-01")
    poisoned.loc[late, "close"] = 1e300
    poisoned.loc[late, "dividend"] = 1e9
    schema.write_parquet(clean, META, tmp_path / "a" / "processed" / "TST.parquet")
    schema.write_parquet(poisoned, META, tmp_path / "b" / "processed" / "TST.parquet")
    a = DataStore(tmp_path / "a").read("TST", date(2004, 1, 1), date(2005, 7, 1))
    b = DataStore(tmp_path / "b").read("TST", date(2004, 1, 1), date(2005, 7, 1))
    for name in ("dates", "close", "log_return", "log_price"):
        np.testing.assert_array_equal(getattr(a, name), getattr(b, name))


def test_invalid_window_rejected(store):
    with pytest.raises(ValueError):
        store.read("TST", date(2005, 1, 1), date(2005, 1, 1))


def test_causal_returns_without_events_is_log_close():
    close = np.array([1.0, 1.1, np.nan, 1.21, 1.0])
    r, p = causal_returns(close, np.zeros(5), np.ones(5))
    np.testing.assert_array_equal(p[[0, 1, 3, 4]], np.log(close[[0, 1, 3, 4]]))
    assert np.isnan(r[0]) and np.isnan(r[2]) and np.isnan(p[2])
    assert r[3] == pytest.approx(np.log(1.21 / 1.1))  # the return after a gap spans the gap


def test_causal_returns_include_dividends_and_carry_events_over_invalid_bars():
    close = np.array([10.0, 10.0, np.nan, 10.0])
    dividend = np.array([0.0, 0.5, 0.0, 0.0])
    r, p = causal_returns(close, dividend, np.ones(4))
    assert r[1] == pytest.approx(np.log(10.5 / 10.0))
    assert p[3] - p[1] == pytest.approx(0.0)
    # a dividend recorded on an invalid bar is credited to the next valid bar
    r2, _ = causal_returns(close, np.array([0.0, 0.0, 0.5, 0.0]), np.ones(4))
    assert np.isnan(r2[2])
    assert r2[3] == pytest.approx(np.log(10.5 / 10.0))


def test_causal_returns_are_prefix_invariant():
    bars = _bars()
    close, div, split = (bars[c].to_numpy() for c in ("close", "dividend", "split"))
    r_full, p_full = causal_returns(close, div, split)
    for n in (10, 151, 500):
        r, p = causal_returns(close[:n], div[:n], split[:n])
        np.testing.assert_array_equal(r, r_full[:n])
        np.testing.assert_array_equal(p, p_full[:n])


@pytest.mark.realdata
def test_real_store_reads_every_instrument(tier_a_dir):
    store = DataStore(tier_a_dir)
    for instrument in store.instruments():
        bars = store.read(instrument, date(2003, 7, 1), date(2007, 7, 1))
        assert bars.dates.max(initial=np.datetime64("1900-01-01")) < np.datetime64("2007-07-01")
