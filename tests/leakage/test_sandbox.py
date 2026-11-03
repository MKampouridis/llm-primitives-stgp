"""Test-period data must be unreachable from modelling code (enforced, not by convention)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.config import load_settings
from lpstgp.data import schema
from lpstgp.data.store import DataStore, modelling_store
from lpstgp.sandbox import Sandbox, SealedPeriodError
from lpstgp.splits import Stage, all_periods, walk_forward

META = {
    "schema_version": 1,
    "instrument_id": "TST",
    "tier": "A",
    "asset_class": "equity_index",
    "calendar": "business",
    "source": "unit",
    "source_symbol": "T",
    "close_only": True,
    "vendor_split_adjusted": False,
    "raw_files": [],
}
PERIOD = walk_forward(date(2005, 7, 1), 1)[0]
LMAX = 504


def _frame(poison_from: str | None = None, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2001-01-01", "2010-12-31")
    frame = pd.DataFrame(
        {"date": dates, "close": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))}
    )
    if poison_from:
        late = frame["date"] >= pd.Timestamp(poison_from)
        frame.loc[late, "close"] = rng.uniform(1e-6, 1e6, late.sum())
        frame.loc[late, "dividend"] = 5.0
    bars, _ = schema.normalise(frame)
    return bars


def _store(tmp_path, name, frame):
    schema.write_parquet(frame, META, tmp_path / name / "processed" / "TST.parquet")
    return DataStore(tmp_path / name)


def test_test_stage_is_sealed(tmp_path):
    store = _store(tmp_path, "clean", _frame())
    with pytest.raises(SealedPeriodError):
        Sandbox.open(store, PERIOD, Stage.TEST, ["TST"], LMAX)


@pytest.mark.parametrize("stage", [Stage.FIT, Stage.VALIDATE])
def test_sandbox_ends_before_horizon_and_has_exact_warmup(tmp_path, stage):
    sandbox = Sandbox.open(_store(tmp_path, "clean", _frame()), PERIOD, stage, ["TST"], LMAX)
    bars = sandbox["TST"]
    assert bars.dates[-1] < np.datetime64(PERIOD.horizon(stage))
    assert np.count_nonzero(bars.dates < np.datetime64(PERIOD.fit_start)) == LMAX
    (record,) = sandbox.access_log
    assert record.warmup_bars == LMAX
    assert record.horizon == PERIOD.horizon(stage)


@pytest.mark.parametrize("stage", [Stage.FIT, Stage.VALIDATE])
def test_poisoned_future_is_invisible(tmp_path, stage):
    """Canary: replace every row from the horizon on with garbage; the sandbox is bit-identical."""
    horizon = PERIOD.horizon(stage).isoformat()
    clean = Sandbox.open(_store(tmp_path, "clean", _frame()), PERIOD, stage, ["TST"], LMAX)["TST"]
    dirty = Sandbox.open(_store(tmp_path, "dirty", _frame(horizon)), PERIOD, stage, ["TST"], LMAX)[
        "TST"
    ]
    for name in ("dates", "close", "log_return", "log_price"):
        np.testing.assert_array_equal(getattr(clean, name), getattr(dirty, name))


def test_fit_is_a_prefix_of_validate(tmp_path):
    store = _store(tmp_path, "clean", _frame())
    fit = Sandbox.open(store, PERIOD, Stage.FIT, ["TST"], LMAX)["TST"]
    val = Sandbox.open(store, PERIOD, Stage.VALIDATE, ["TST"], LMAX)["TST"]
    n = len(fit)
    for name in ("dates", "close", "log_return", "log_price"):
        np.testing.assert_array_equal(getattr(fit, name), getattr(val, name)[:n])


def test_sandbox_holds_no_store_and_arrays_are_read_only(tmp_path):
    sandbox = Sandbox.open(_store(tmp_path, "clean", _frame()), PERIOD, Stage.FIT, ["TST"], LMAX)
    assert not any(isinstance(v, DataStore) for v in vars(sandbox).values())
    with pytest.raises(ValueError, match="read-only"):
        sandbox["TST"].close[0] = 1.0


def test_scored_masks(tmp_path):
    store = _store(tmp_path, "clean", _frame())
    fit = Sandbox.open(store, PERIOD, Stage.FIT, ["TST"], LMAX)
    val = Sandbox.open(store, PERIOD, Stage.VALIDATE, ["TST"], LMAX)
    fit_dates = fit["TST"].dates[fit.scored_mask("TST")]
    val_dates = val["TST"].dates[val.scored_mask("TST")]
    assert fit_dates.min() >= np.datetime64(PERIOD.fit_start)
    assert fit_dates.max() < np.datetime64(PERIOD.val_start)
    assert val_dates.min() >= np.datetime64(PERIOD.val_start)
    assert val_dates.max() < np.datetime64(PERIOD.test_start)
    assert fit.key != val.key


@pytest.mark.realdata
def test_real_sandboxes_never_reach_their_horizon(tier_a_dir):
    """Every period's FIT and VALIDATE stages through the modelling store (D-080): no bar at or
    after the stage's horizon, for every instrument; TEST stays sealed."""
    settings = load_settings()
    store = modelling_store(tier_a_dir, settings)
    lmax = settings["splits"]["lookback_max_bars"]
    periods = all_periods(settings)
    with pytest.raises(SealedPeriodError, match="sealed"):
        Sandbox.open(store, periods["P01"], Stage.TEST, store.instruments(), lmax)
    for period in periods.values():
        for stage in (Stage.FIT, Stage.VALIDATE):
            sandbox = Sandbox.open(store, period, stage, store.instruments(), lmax)
            for instrument in sandbox.instruments:
                dates = sandbox[instrument].dates
                if len(dates):
                    assert dates[-1] < np.datetime64(period.horizon(stage))
