import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from lpstgp.data import schema


def frame(**columns):
    base = {"date": pd.to_datetime(["2005-01-03", "2005-01-04", "2005-02-01", "2005-02-02"])}
    base.update(columns)
    return pd.DataFrame(base)


META = {
    "schema_version": 1,
    "instrument_id": "TEST",
    "tier": "A",
    "asset_class": "equity_index",
    "calendar": "business",
    "source": "unit",
    "source_symbol": "T",
    "close_only": False,
    "vendor_split_adjusted": False,
    "raw_files": [],
}


def test_normalise_adds_defaults_and_orders_columns():
    bars, flags = schema.normalise(frame(close=[1.0, 2.0, 3.0, 4.0]))
    assert list(bars.columns) == list(schema.COLUMNS)
    assert bars["dividend"].eq(0).all()
    assert bars["split"].eq(1).all()
    assert bars[["open", "high", "low", "volume"]].isna().all().all()
    assert flags.empty


def test_nonpositive_close_is_invalidated_and_flagged():
    bars, flags = schema.normalise(
        frame(close=[1.0, -36.98, 0.0, np.nan], open=[1.0, 1.0, 1.0, 1.0])
    )
    assert np.isnan(bars["close"].iloc[1])
    assert np.isnan(bars["open"].iloc[1])
    assert np.isnan(bars["close"].iloc[2])
    assert list(flags["flag"]) == [
        "invalid_close",
        "invalid_close",
    ]  # a missing close is not flagged


def test_ohlc_violation_keeps_close_drops_extremes():
    bars, flags = schema.normalise(
        frame(open=[1.0] * 4, high=[2.0, 0.5, 2.0, 2.0], low=[0.5] * 4, close=[1.5, 0.9, 1.5, 1.5])
    )
    assert bars["close"].iloc[1] == 0.9
    assert bars.loc[1, ["open", "high", "low"]].isna().all()
    assert list(flags["flag"]) == ["ohlc_violation"]


def test_events_are_cleaned():
    bars, flags = schema.normalise(
        frame(close=[1.0] * 4, dividend=[np.nan, -1.0, 0.25, 0.0], split=[np.nan, 0.0, 2.0, 1.0])
    )
    assert list(bars["dividend"]) == [0.0, 0.0, 0.25, 0.0]
    assert list(bars["split"]) == [1.0, 1.0, 2.0, 1.0]
    assert list(flags["flag"]) == ["invalid_dividend"]


def test_duplicates_are_rejected():
    dup = pd.DataFrame({"date": pd.to_datetime(["2005-01-03", "2005-01-03"]), "close": [1.0, 1.1]})
    with pytest.raises(schema.SchemaError):
        schema.normalise(dup)


def test_rows_are_sorted():
    unsorted = pd.DataFrame(
        {"date": pd.to_datetime(["2005-01-04", "2005-01-03"]), "close": [2.0, 1.0]}
    )
    bars, _ = schema.normalise(unsorted)
    assert list(bars["close"]) == [1.0, 2.0]


def test_roundtrip_with_monthly_row_groups(tmp_path):
    bars, _ = schema.normalise(frame(close=[1.0, 2.0, 3.0, 4.0], volume=[10.0, 11.0, 12.0, 13.0]))
    path = tmp_path / "TEST.parquet"
    schema.write_parquet(bars, META, path)
    assert pq.ParquetFile(path).num_row_groups == 2  # January and February
    back = schema.read_frame(path)
    pd.testing.assert_frame_equal(
        back.reset_index(drop=True), bars.reset_index(drop=True), check_dtype=False
    )
    assert schema.read_meta(path)["instrument_id"] == "TEST"


def test_write_requires_metadata(tmp_path):
    bars, _ = schema.normalise(frame(close=[1.0, 2.0, 3.0, 4.0]))
    with pytest.raises(schema.SchemaError):
        schema.write_parquet(bars, {"instrument_id": "X"}, tmp_path / "X.parquet")


def test_normalise_is_row_local():
    """Building from a prefix gives exactly the prefix of the full build (causal build)."""
    rng = np.random.default_rng(0)
    n = 300
    raw = pd.DataFrame(
        {
            "date": pd.bdate_range("2005-01-03", periods=n),
            "open": rng.uniform(0.5, 1.5, n),
            "high": rng.uniform(1.0, 2.0, n),
            "low": rng.uniform(0.2, 1.2, n),
            "close": rng.uniform(-0.2, 1.8, n),
            "dividend": rng.choice([0.0, 0.1, np.nan], n),
        }
    )
    full, full_flags = schema.normalise(raw)
    for cut in (1, 57, 200, n - 1):
        part, part_flags = schema.normalise(raw.iloc[:cut])
        pd.testing.assert_frame_equal(part, full.iloc[:cut])
        expected_flags = full_flags[full_flags["date"] < raw["date"].iloc[cut]].reset_index(
            drop=True
        )
        pd.testing.assert_frame_equal(
            part_flags.reset_index(drop=True), expected_flags, check_dtype=False
        )
