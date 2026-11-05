"""GP development periods G1-G3 (D-092): long fits, validation before WP4's first test year,
and no test stage at all."""

from datetime import date

import pytest

from lpstgp.config import load_settings
from lpstgp.splits import Stage, all_periods, periods_from_settings

SETTINGS = load_settings()


def test_validation_years_end_by_p01s_test_start_and_there_is_no_test_year():
    periods = all_periods(SETTINGS)
    p01 = periods_from_settings(SETTINGS)[0]
    for pid, val in (("G1", date(2005, 7, 1)), ("G2", date(2006, 7, 1)), ("G3", date(2007, 7, 1))):
        p = periods[pid]
        assert p.val_start == val
        assert (p.val_start - p.fit_start).days >= 6 * 365
        assert p.horizon(Stage.VALIDATE) <= p01.test_start
        assert p.test_end == p.test_start  # an empty test stage
        assert pid in SETTINGS["leakage"]["allowed_periods"]


def test_e4_periods_are_fresh_six_year_fits_ending_before_g1s_validation_year():
    periods = all_periods(SETTINGS)
    for k in range(1, 8):
        p = periods[f"H{k}"]
        assert p.val_start == date(1997 + k, 7, 1)
        assert (p.val_start - p.fit_start).days >= 6 * 365
        assert p.test_end == p.test_start <= periods["G1"].val_start


def _store(root, poison_from=None):
    import numpy as np
    import pandas as pd

    from lpstgp.data import schema
    from lpstgp.data.store import DataStore

    rng = np.random.default_rng(3)
    dates = pd.bdate_range("1988-01-04", "2010-12-31")
    frame = pd.DataFrame({"date": dates,
                          "close": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))})  # fmt: skip
    if poison_from:
        late = frame["date"] >= pd.Timestamp(poison_from)
        frame.loc[late, "close"] = rng.uniform(1e-6, 1e6, late.sum())
    bars, _ = schema.normalise(frame)
    meta = {"schema_version": 1, "instrument_id": "TST", "tier": "A",
            "asset_class": "equity_index", "calendar": "business", "source": "unit",
            "source_symbol": "T", "close_only": True, "vendor_split_adjusted": False,
            "raw_files": []}  # fmt: skip
    schema.write_parquet(bars, meta, root / "processed" / "TST.parquet")
    return DataStore(root, periods=all_periods(SETTINGS))


@pytest.mark.parametrize("pid", ["G1", "G2", "G3", "H1", "H7"])
def test_their_sandboxes_ignore_a_poisoned_future_and_the_test_stage_is_sealed(tmp_path, pid):
    import numpy as np

    from lpstgp.sandbox import Sandbox, SealedPeriodError

    period = all_periods(SETTINGS)[pid]
    clean = Sandbox.open(_store(tmp_path / "c"), period, Stage.VALIDATE, ["TST"], 504)["TST"]
    dirty = Sandbox.open(_store(tmp_path / "d", period.test_start.isoformat()), period,
                         Stage.VALIDATE, ["TST"], 504)["TST"]  # fmt: skip
    assert clean.dates[-1] < np.datetime64(period.test_start)
    np.testing.assert_array_equal(clean.close, dirty.close)
    with pytest.raises(SealedPeriodError):
        Sandbox.open(_store(tmp_path / "t"), period, Stage.TEST, ["TST"], 504)
