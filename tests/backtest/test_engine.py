import numpy as np
import pytest

from lpstgp.backtest import engine, metrics
from lpstgp.backtest.costs import CostModel, from_meta

NAN = np.nan
FREE = CostModel(0.0, 0.0)


def test_state_machine():
    entry = np.array([0, 1, 1, 0, 1, NAN, 0, 1])
    exit_ = np.array([0, 0, 0, 1, 1, 0, NAN, 0])
    # t1 enter; t2 stay; t3 exit; t4 entry and exit together while flat -> stay flat;
    # t5 entry unknown -> no action; t6 exit unknown -> nothing; t7 enter
    np.testing.assert_array_equal(engine.decide(entry, exit_, 0), [0, 1, 1, 0, 0, 0, 0, 1])


def test_long_position_exits_even_if_entry_is_true():
    entry = np.array([1, 1, 1.0])
    exit_ = np.array([0, 1, 0.0])
    np.testing.assert_array_equal(engine.decide(entry, exit_, 0), [1, 0, 1])


def test_unknown_exit_does_not_block_entry():
    np.testing.assert_array_equal(engine.decide(np.array([1.0]), np.array([NAN]), 0), [1])


def test_rule_is_flat_before_active_from():
    entry = np.ones(5)
    np.testing.assert_array_equal(engine.decide(entry, np.zeros(5), 3), [0, 0, 0, 1, 1])


def test_one_bar_execution_shift_and_returns():
    log_return = np.log(np.array([1.0, 1.10, 0.90, 1.05, 1.0]))
    entry = np.array([0, 1, 0, 0, 0.0])  # signal at the close of bar 1
    exit_ = np.array([0, 0, 0, 1, 0.0])  # exit signal at the close of bar 3
    res = engine.run(entry, exit_, log_return, FREE)
    np.testing.assert_array_equal(res.held, [0, 0, 1, 1, 0])  # held over bars 2 and 3
    np.testing.assert_allclose(res.net, [0, 0, -0.10, 0.05, 0])
    lagged = engine.run(entry, exit_, log_return, FREE, lag=2)
    np.testing.assert_array_equal(lagged.held, [0, 0, 0, 1, 1])


def test_costs_charged_on_position_changes():
    log_return = np.zeros(6)
    entry = np.array([1, 0, 0, 0, 0, 0.0])
    exit_ = np.array([0, 0, 1, 0, 0, 0.0])
    costs = CostModel(buy_bps=10.0, sell_bps=60.0)
    res = engine.run(entry, exit_, log_return, costs)
    # held = [0, 1, 1, 0, 0, 0]: buy at bar 1 (10 bps), sell at bar 3 (60 bps)
    np.testing.assert_allclose(res.cost, [0, 1e-3, 0, 6e-3, 0, 0])
    doubled = engine.run(entry, exit_, log_return, costs.scaled(2.0))
    np.testing.assert_allclose(doubled.cost.sum(), 2 * res.cost.sum())
    assert from_meta({"cost_bps": 3.0}).buy_bps == 3.0


def test_invalid_returns_contribute_nothing():
    res = engine.run(np.ones(3), np.zeros(3), np.array([NAN, NAN, 0.1]), FREE)
    np.testing.assert_allclose(res.net, [0, 0, np.expm1(0.1)])


def test_batch_equals_single():
    rng = np.random.default_rng(0)
    entry = (rng.random((5, 200)) < 0.1).astype(float)
    exit_ = (rng.random((5, 200)) < 0.1).astype(float)
    log_return = rng.normal(0, 0.01, 200)
    costs = CostModel(2.0, 2.0)
    batch = engine.run(entry, exit_, log_return, costs, active_from=np.array([0, 5, 10, 0, 50]))
    for k, start in enumerate([0, 5, 10, 0, 50]):
        single = engine.run(entry[k], exit_[k], log_return, costs, active_from=start)
        np.testing.assert_array_equal(batch.net[k], single.net)


def test_no_look_ahead():
    """Returns up to bar t never depend on signals after bar t - lag."""
    rng = np.random.default_rng(1)
    entry = (rng.random(300) < 0.1).astype(float)
    exit_ = (rng.random(300) < 0.1).astype(float)
    log_return = rng.normal(0, 0.01, 300)
    base = engine.run(entry, exit_, log_return, CostModel(1.0, 1.0))
    for t in (50, 150, 299):
        e2, x2 = entry.copy(), exit_.copy()
        e2[t:] = rng.random(300 - t) < 0.5
        x2[t:] = rng.random(300 - t) < 0.5
        other = engine.run(e2, x2, log_return, CostModel(1.0, 1.0))
        np.testing.assert_array_equal(other.net[: t + 1], base.net[: t + 1])


def test_metrics_reference_values():
    net = np.array([0.01, -0.02, 0.03, -0.01, 0.0])
    assert metrics.sharpe(net, 252) == pytest.approx(net.mean() / net.std(ddof=1) * np.sqrt(252))
    equity = np.cumprod(1 + net)
    peak = np.maximum.accumulate(np.maximum(equity, 1.0))
    assert metrics.max_drawdown(net) == pytest.approx(np.max(1 - equity / peak))
    assert metrics.sharpe(np.zeros(10), 252) == 0.0
    held = np.array([0, 1, 1, 0, 1, 1, 1, 0.0])
    assert metrics.trades(held) == 2
    assert metrics.turnover(held, 252) == pytest.approx(4 * 252 / 8)
    assert metrics.exposure(held) == pytest.approx(5 / 8)
    s = metrics.summary(net, held[:5], 252)
    assert set(s) >= {
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "total_return",
        "turnover",
        "trades",
    }
