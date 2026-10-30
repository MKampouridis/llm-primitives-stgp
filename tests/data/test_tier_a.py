from collections import Counter
from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.data import manifest as mf
from lpstgp.data import schema, tier_a
from lpstgp.data.store import DataStore


def test_universe_composition():
    universe = tier_a.load_universe()
    classes = Counter(i.asset_class for i in universe)
    assert classes == {"equity_index": 10, "fx": 8, "commodity": 6, "bond": 2, "crypto": 5}
    assert all(i.cost_bps > 0 for i in universe)
    assert {i.calendar for i in universe if i.asset_class == "crypto"} == {"7day"}
    assert {i.calendar for i in universe if i.asset_class != "crypto"} == {"business"}


def test_series_components_are_unique():
    components = tier_a.series_components(tier_a.load_universe(), include_alternates=True)
    assert len(components) == len(set(components))
    assert ("ecb", "USD") in components
    assert ("ecb", "GBP") in components


def _write_raw(tier_dir, source, symbol, content: bytes, suffix: str, day="20261030"):
    path = tier_a.raw_dir(tier_dir, source, symbol) / f"{day}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    mf.append_entry(
        tier_dir / "manifest.csv",
        {
            "source": source,
            "symbol": symbol,
            "downloaded_at_utc": f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00+00:00",
            "file": str(path.relative_to(tier_dir)),
            "bytes": len(content),
            "sha256": mf.sha256_bytes(content),
        },
    )


def _ecb_csv(currency: str, dates, values) -> bytes:
    rows = "\n".join(
        f"EXR.D.{currency}.EUR.SP00.A,{d},{v}" for d, v in zip(dates, values, strict=True)
    )
    return f"KEY,TIME_PERIOD,OBS_VALUE\n{rows}\n".encode()


def _instrument(primary: tier_a.SeriesRef) -> tier_a.Instrument:
    return tier_a.Instrument(
        "XUSD", "Test pair", "fx", "Global", "USD", "business", "", 1.0, primary
    )


@pytest.fixture
def ecb_tier(tmp_path):
    dates = [str(d.date()) for d in pd.bdate_range("2004-01-01", "2006-12-29")]
    rng = np.random.default_rng(1)
    usd = np.round(1.2 + rng.normal(0, 0.01, len(dates)).cumsum(), 4)
    gbp = np.round(0.7 + rng.normal(0, 0.005, len(dates)).cumsum(), 4)
    usd[100] = np.nan
    _write_raw(tmp_path, "ecb", "USD", _ecb_csv("USD", dates, usd), ".csv")
    _write_raw(tmp_path, "ecb", "GBP", _ecb_csv("GBP", dates[5:], gbp[5:]), ".csv")
    return tmp_path, dates


def test_build_cross_rate_and_metadata(ecb_tier):
    tier_dir, _ = ecb_tier
    inst = _instrument(tier_a.SeriesRef("ecb", "USD", divide_by="GBP"))
    path, bars, _ = tier_a.build_series(inst, inst.primary, tier_dir, date(2026, 6, 30), "primary")
    meta = schema.read_meta(path)
    assert meta["source_symbol"] == "USD/GBP"
    assert meta["close_only"] is True
    assert len(meta["raw_files"]) == 2
    assert bars["date"].min() > pd.Timestamp("2004-01-07")  # common dates only
    assert bars[["open", "high", "low"]].isna().all().all()


def test_build_drops_rows_after_design_end(ecb_tier):
    tier_dir, _ = ecb_tier
    inst = _instrument(tier_a.SeriesRef("ecb", "USD"))
    _, bars, _ = tier_a.build_series(inst, inst.primary, tier_dir, date(2005, 6, 30), "primary")
    assert bars["date"].max() <= pd.Timestamp("2005-06-30")


def test_causal_build(ecb_tier, tmp_path_factory):
    """Building from raw files cut at date d reproduces every earlier row bit for bit."""
    tier_dir, _dates = ecb_tier
    inst = _instrument(tier_a.SeriesRef("ecb", "USD", divide_by="GBP"))
    _, full, _ = tier_a.build_series(inst, inst.primary, tier_dir, date(2026, 6, 30), "primary")
    for cut in ("2004-03-15", "2005-07-01", "2006-06-30"):
        cut_dir = tmp_path_factory.mktemp("cut")
        for currency in ("USD", "GBP"):
            frame = pd.read_csv(tier_a.raw_dir(tier_dir, "ecb", currency) / "20261030.csv")
            frame = frame[frame["TIME_PERIOD"] < cut]
            _write_raw(cut_dir, "ecb", currency, frame.to_csv(index=False).encode(), ".csv")
        _, part, _ = tier_a.build_series(inst, inst.primary, cut_dir, date(2026, 6, 30), "primary")
        expected = full[full["date"] < pd.Timestamp(cut)].reset_index(drop=True)
        pd.testing.assert_frame_equal(part.reset_index(drop=True), expected)


def test_checksum_mismatch_is_detected(ecb_tier):
    tier_dir, _ = ecb_tier
    raw = tier_a.raw_dir(tier_dir, "ecb", "USD") / "20261030.csv"
    raw.write_bytes(raw.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        tier_a.load_raw_series(tier_dir, "ecb", "USD")


@pytest.mark.realdata
def test_every_primary_is_built(tier_a_dir):
    store = DataStore(tier_a_dir)
    available = set(store.instruments())
    missing = [i.id for i in tier_a.load_universe() if i.id not in available]
    assert missing == []
