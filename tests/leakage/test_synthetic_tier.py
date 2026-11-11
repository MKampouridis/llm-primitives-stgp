"""Tier S (synthetic planted-signal worlds, D-101) is read like any other tier: through the
sandbox, FIT and VALIDATE only, on G1's dates; a poisoned future never reaches a sandbox."""

import numpy as np
import pandas as pd
import pytest

from lpstgp.config import load_settings
from lpstgp.data import synthetic
from lpstgp.data.store import DataStore
from lpstgp.sandbox import Sandbox, SealedPeriodError
from lpstgp.splits import Stage, all_periods

SETTINGS = load_settings()
G1 = all_periods(SETTINGS)["G1"]


def _store(root, poison_from=None):
    dates = pd.bdate_range("1994-01-03", "2008-12-31").to_numpy().astype("datetime64[D]")
    close, _ = synthetic.simulate(len(dates), 1, 4)
    if poison_from is not None:
        late = dates >= np.datetime64(poison_from)
        close[late] = np.random.default_rng(1).uniform(1e-6, 1e6, (late.sum(), 1))
    synthetic.write_world(root, ("syn",), dates, close, {"world": "w", "rule": "null"}, 2.0)
    return DataStore(root, max_horizon=SETTINGS["leakage"]["max_horizon"],
                     periods=all_periods(SETTINGS))  # fmt: skip


@pytest.mark.parametrize("stage", [Stage.FIT, Stage.VALIDATE])
def test_a_poisoned_future_never_reaches_a_tier_s_sandbox(tmp_path, stage):
    horizon = G1.horizon(stage)
    clean = Sandbox.open(_store(tmp_path / "c"), G1, stage, ["syn"], 504)["syn"]
    dirty = Sandbox.open(_store(tmp_path / "d", horizon), G1, stage, ["syn"], 504)["syn"]
    assert clean.dates[-1] < np.datetime64(horizon)
    np.testing.assert_array_equal(clean.close, dirty.close)
    np.testing.assert_array_equal(clean.log_return, dirty.log_return)
    assert np.count_nonzero(clean.dates < np.datetime64(G1.fit_start)) == 504  # full warm-up


def test_the_test_stage_of_tier_s_is_sealed_like_any_other(tmp_path):
    assert G1.test_end == G1.test_start  # G1 has no test year at all
    with pytest.raises(SealedPeriodError):
        Sandbox.open(_store(tmp_path), G1, Stage.TEST, ["syn"], 504)
