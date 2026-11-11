"""Synthetic planted-signal worlds (tier S, D-101): the generator is causal, prefix-invariant
and reproducible, plants the edge it says it plants, and writes files the store reads back."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.data import synthetic
from lpstgp.data.store import DataStore

LOOKBACK = 21


def momentum(log_price, log_return):
    """Long after a rise over the window, short after a fall (a toy planted rule)."""
    assert len(log_price) == len(log_return) == LOOKBACK  # only the window, ending at the bar
    return float(log_price[-1] > log_price[0])


def test_a_longer_simulation_repeats_a_shorter_one_exactly():
    short = synthetic.simulate(300, 3, 7, 1.0, momentum, LOOKBACK)
    long = synthetic.simulate(420, 3, 7, 1.0, momentum, LOOKBACK)
    np.testing.assert_array_equal(short[0], long[0][:300])
    np.testing.assert_array_equal(short[1], long[1][:300])
    again = synthetic.simulate(300, 3, 7, 1.0, momentum, LOOKBACK)
    np.testing.assert_array_equal(short[0], again[0])
    assert not np.array_equal(short[0], synthetic.simulate(300, 3, 8, 1.0, momentum, LOOKBACK)[0])


def test_a_bar_depends_only_on_decisions_made_at_least_lag_bars_earlier():
    """Poisoned-future canary: flipping every decision from bar T on leaves the closes up to
    bar T + lag - 1 untouched and changes later ones."""
    n, k, lag, flip_at = 260, 2, 2, 150
    calls = {"n": 0}

    def flipped(log_price, log_return):
        bar = LOOKBACK - 1 + calls["n"] // k  # the bar being decided (k calls a bar)
        calls["n"] += 1
        value = momentum(log_price, log_return)
        return 1.0 - value if bar >= flip_at else value

    clean, _ = synthetic.simulate(n, k, 5, 2.0, momentum, LOOKBACK, lag=lag)
    dirty, _ = synthetic.simulate(n, k, 5, 2.0, flipped, LOOKBACK, lag=lag)
    np.testing.assert_array_equal(clean[: flip_at + lag], dirty[: flip_at + lag])
    assert (clean[flip_at + lag] != dirty[flip_at + lag]).all()


def test_the_planted_rule_earns_its_sharpe_and_a_null_world_has_no_edge():
    n, k, lag = 6000, 4, 2
    close, position = synthetic.simulate(n, k, 11, 2.0, momentum, LOOKBACK, lag=lag)
    assert set(np.unique(position[~np.isnan(position)])) == {-1.0, 1.0}
    assert np.isnan(position[: LOOKBACK - 1]).all()
    assert not np.isnan(position[LOOKBACK:]).any()
    returns = np.diff(np.log(close), axis=0)
    pnl = position[LOOKBACK : n - lag] * returns[LOOKBACK + lag - 1 :]  # held lag bars later
    planted = pnl.mean(axis=0) / pnl.std(axis=0) * np.sqrt(252)
    assert 1.4 < planted.mean() < 2.6
    null_close, null_position = synthetic.simulate(n, k, 11)
    assert np.isnan(null_position).all()
    null_returns = np.diff(np.log(null_close), axis=0)
    # the same shocks without the drift: the toy rule's positions earn nothing on them
    lp = np.log(null_close)
    toy = np.where(lp[LOOKBACK - 1 : n - lag] > lp[: n - lag - LOOKBACK + 1], 1.0, -1.0)
    null_pnl = toy * null_returns[LOOKBACK + lag - 2 :]
    assert abs((null_pnl.mean(axis=0) / null_pnl.std(axis=0) * np.sqrt(252)).mean()) < 0.5
    vol = null_returns.std(axis=0) * np.sqrt(252)
    assert np.all((vol > 0.13) & (vol < 0.24))
    assert 0.35 < np.corrcoef(null_returns.T)[0, 1] < 0.65


def test_zero_sharpe_or_no_signal_is_pure_noise_and_bad_inputs_are_refused():
    a, _ = synthetic.simulate(120, 2, 3)
    b, planted = synthetic.simulate(120, 2, 3, 0.0, momentum, LOOKBACK)
    np.testing.assert_array_equal(a, b)
    assert np.isnan(planted).all()
    with pytest.raises(ValueError, match="lookback"):
        synthetic.simulate(50, 1, 3, 1.0, momentum)
    with pytest.raises(ValueError, match="GARCH"):
        synthetic.NoiseModel(alpha=0.2, beta=0.9)
    assert synthetic.world_seed("trend100w1") == synthetic.world_seed("trend100w1")
    assert synthetic.world_seed("trend100w1") != synthetic.world_seed("trend100w2")


def test_written_worlds_read_back_through_the_store_as_the_generator_saw_them(tmp_path):
    dates = pd.bdate_range("2000-01-03", periods=400).to_numpy().astype("datetime64[D]")
    close, _ = synthetic.simulate(400, 2, 9, 1.0, momentum, LOOKBACK)
    planted = {"world": "w", "rule": "toy", "sharpe": 1.0, "entry": "E", "exit": "X"}
    paths = synthetic.write_world(tmp_path, ("syna", "synb"), dates, close, planted, 2.0)
    assert [p.name for p in paths] == ["syna.parquet", "synb.parquet"]
    store = DataStore(tmp_path)
    assert store.instruments() == ["syna", "synb"]
    bars = store.read("synb", date(2000, 1, 1), date(2002, 1, 1))
    np.testing.assert_array_equal(bars.close, close[:, 1])
    np.testing.assert_array_equal(bars.log_price, np.log(close[:, 1]))
    np.testing.assert_array_equal(bars.log_return[1:], np.diff(np.log(close[:, 1])))
    assert bars.meta["tier"] == "S"
    assert bars.meta["cost_bps"] == 2.0
    assert bars.meta["planted"] == planted
    assert bars.meta["noise"]["rho"] == 0.5
    # the horizon still cuts: nothing at or after it is read
    early = store.read("synb", date(2000, 1, 1), date(2000, 7, 1))
    assert early.dates[-1] < np.datetime64("2000-07-01")
