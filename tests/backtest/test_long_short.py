"""Stop-and-reverse long-short and volatility-targeted positions (GP development E2, D-094)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.backtest import engine
from lpstgp.backtest.costs import CostModel
from lpstgp.campaign.plan import Config
from lpstgp.config import load_settings
from lpstgp.gp.fitness import (
    VOL_CAP,
    FitnessConfig,
    market_part,
    prepare,
    trailing_vol,
    vol_scale,
)

NAN = np.nan


def test_reverse_goes_long_on_entry_short_on_exit_and_ignores_unknown_or_conflicting_bars():
    entry = np.array([0, 1, 0, NAN, 0, 1, 1, 0, 0])
    exit_ = np.array([0, 0, 0, 0, 1, 1, 0, NAN, 0])
    got = engine.decide_reverse(entry.astype(float), exit_.astype(float), 0)
    np.testing.assert_array_equal(got, [0, 1, 1, 1, -1, -1, 1, 1, 1])
    assert (
        engine.decide_reverse(entry.astype(float), exit_.astype(float), 5)[:5].tolist() == [0] * 5
    )


def test_long_only_is_unchanged_by_the_new_arguments():
    rng = np.random.default_rng(0)
    lr = rng.normal(0, 0.01, 300)
    entry = (rng.random(300) < 0.1).astype(float)
    exit_ = (rng.random(300) < 0.1).astype(float)
    a = engine.run(entry, exit_, lr, CostModel(5, 5), lag=2)
    b = engine.run(entry, exit_, lr, CostModel(5, 5), lag=2, mode="long_only", scale=None)
    np.testing.assert_array_equal(a.net, b.net)
    with pytest.raises(ValueError, match="position mode"):
        engine.run(entry, exit_, lr, CostModel(5, 5), mode="sideways")


def test_a_short_position_earns_a_fall_and_pays_costs_on_every_change_and_resize():
    lr = np.log(np.array([1.0, 0.99, 0.98, 0.97, 1.0, 1.0]))  # falls, then flat
    entry = np.zeros(6)
    exit_ = np.array([1.0, 0, 0, 0, 0, 0])  # short from the first close
    res = engine.run(entry, exit_, lr, CostModel(0, 0), lag=1, mode="reverse")
    np.testing.assert_array_equal(res.held, [0, -1, -1, -1, -1, -1])
    assert res.net[1] == pytest.approx(0.01)
    scale = np.array([1.0, 2.0, 2.0, 1.0, 1.0, 1.0])
    sized = engine.run(entry, exit_, lr, CostModel(10, 10), lag=1, mode="reverse", scale=scale)
    np.testing.assert_array_equal(sized.held, [0, -1, -2, -2, -1, -1])  # decision t-1 x scale t-1
    assert sized.cost[1] == pytest.approx(1e-3)  # open 1 unit at 10 bp
    assert sized.cost[2] == pytest.approx(1e-3)  # resize by 1 unit
    assert sized.cost[3] == 0.0


def test_trailing_volatility_and_sizing_use_only_bars_up_to_each_close():
    """Poisoned future: changing later returns never changes an earlier volatility or size."""
    rng = np.random.default_rng(1)
    lr = rng.normal(0, 0.01, 400)
    v = trailing_vol(lr, 63, 252)
    assert np.isnan(v[61])
    assert np.isfinite(v[62])
    poisoned = lr.copy()
    poisoned[300:] = rng.normal(0, 0.5, 100)
    np.testing.assert_array_equal(trailing_vol(poisoned, 63, 252)[:300], v[:300])
    s = vol_scale(v, 0.10)
    assert s[:62].tolist() == [0.0] * 62
    assert np.nanmax(s) <= VOL_CAP
    assert np.median(s[62:]) == pytest.approx(0.10 / (0.01 * np.sqrt(252)), rel=0.15)


def _scored(lr, dates):
    return prepare(dates, lr, "business", (date(2004, 1, 1), date(2006, 1, 1)), CostModel(1, 1), 6)


def test_volatility_targeted_long_short_fitness_hits_the_target_and_reads_no_future():
    dates = pd.bdate_range("2002-01-01", periods=1100).to_numpy().astype("datetime64[D]")
    rng = np.random.default_rng(2)
    lr = rng.normal(2e-4, 0.02, len(dates))  # 32% a year: sized down to about 10%
    data = _scored(lr, dates)
    mom = np.r_[np.full(20, np.nan), np.sign(lr[20:] - lr[:-20])]
    entry, exit_ = (mom > 0).astype(float), (mom < 0).astype(float)
    cfg = FitnessConfig(position_mode="reverse", vol_target=0.10, min_entries_per_year=0.0)
    value, parts = market_part(entry, exit_, data, cfg)
    assert parts["exposure"] == pytest.approx(1.0, abs=0.01)  # always in the market
    res = engine.run(entry, exit_, lr, CostModel(1, 1), active_from=data.active_from, lag=2,
                     mode="reverse", scale=vol_scale(data.vol, 0.10))  # fmt: skip
    realised = res.net[data.active_from : data.stop].std() * np.sqrt(252)
    assert realised == pytest.approx(0.10, rel=0.2)
    poisoned = lr.copy()
    poisoned[data.stop :] = 0.4
    assert market_part(entry, exit_, _scored(poisoned, dates), cfg)[0] == value


def test_new_position_settings_leave_earlier_digests_unchanged():
    settings = load_settings()
    plain = Config("a", "s2c", gp={"population": 250})
    same = Config("a", "s2c", gp={"population": 250},
                  fitness={"position_mode": "long_only", "vol_target": 0.0})  # fmt: skip
    assert plain.digest(settings) == same.digest(settings)
    e2 = Config("a", "s2c", gp={"population": 250},
                fitness={"position_mode": "reverse", "vol_target": 0.10})  # fmt: skip
    assert e2.digest(settings) != plain.digest(settings)
    with pytest.raises(ValueError, match="position mode"):
        FitnessConfig(position_mode="short_only")


def test_the_sharpe_objective_scores_slow_trend_rules_by_their_sharpe_ratio():
    """E3 (D-096): a rule trading rarely is scored, not floored, once the activity rule is off."""
    dates = pd.bdate_range("2002-01-01", periods=1100).to_numpy().astype("datetime64[D]")
    lr = np.random.default_rng(4).normal(3e-4, 0.01, len(dates))
    data = _scored(lr, dates)
    entry = np.zeros(len(dates))
    entry[data.active_from] = 1.0  # long once, held
    cfg = FitnessConfig(position_mode="reverse", vol_target=0.10, objective="sharpe",
                        min_entries_per_year=0.0)  # fmt: skip
    value, parts = market_part(entry, np.zeros(len(dates)), data, cfg)
    assert value == parts["sharpe"] != cfg.no_trade_value
    floored = FitnessConfig(position_mode="reverse", vol_target=0.10, objective="sharpe")
    assert market_part(entry, np.zeros(len(dates)), data, floored)[0] == floored.no_trade_value
