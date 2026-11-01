"""Arms 1, 2a, 2b and 2c built from (toy) frozen strategies, on synthetic sandboxes."""

from pathlib import Path

import numpy as np
import pytest
from tests.gp.conftest import INSTRUMENTS, PERIOD
from tests.gp.test_run import COSTS, TINY, tiny_run

from lpstgp.gp.evaluate import TreeEvaluator
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.pset import build
from lpstgp.libraries import resolve
from lpstgp.operators.contract import Provenance
from lpstgp.strategies import registry, selection
from lpstgp.strategies.adapters import Frozen
from lpstgp.strategies.loader import load_file

FIXTURES = Path(__file__).parents[1] / "strategies" / "fixtures"
TEST_PROVENANCE = Provenance("test fixture", "tests", "2026-10-31")


@pytest.fixture(scope="module")
def frozen():
    files = ("toy_trend.py", "toy_reversal.py")
    return tuple(
        Frozen(f"s{k + 1:02d}", load_file(FIXTURES / name), "0" * 64, TEST_PROVENANCE)
        for k, name in enumerate(files)
    )


@pytest.mark.parametrize("arm", ["s2a", "s2b", "s2c"])
def test_strategy_arms_build_and_run_reproducibly(arm, frozen, fit_box, val_box):
    lib = build(resolve(arm, frozen))
    a = tiny_run(lib, fit_box, val_box, seed=3)
    b = tiny_run(lib, fit_box, val_box, seed=3)
    assert a["hall_of_fame"]
    assert [h["entry_str"] for h in a["hall_of_fame"]] == [
        h["entry_str"] for h in b["hall_of_fame"]
    ]
    best = a["hall_of_fame"][a["selected"]]
    assert best["lookback"] <= 504


def test_library_contents(frozen):
    names_2a = {s.name for s in resolve("s2a", frozen)}
    assert {"s01_entry", "s01_exit", "s02_entry", "s02_exit", "and", "or", "not"} == names_2a
    names_2b = {s.name for s in resolve("s2b", frozen)}
    assert {"s01_trend", "s01_volatility", "s01_gap", "s02_range_position"} <= names_2b
    assert not {"log_price", "ret", "rolling_hist"} & names_2b  # no data terminals or Hist glue
    ops_2c = {s.name: s for s in resolve("s2c", frozen)}
    assert {"log_price", "ret", "abs_ret"} <= set(ops_2c)
    assert [p.name for p in ops_2c["s02_range_position"].params] == ["window", "q"]


def _evaluate(lib, box, text):
    from deap import gp

    tree = gp.PrimitiveTree.from_string(text, lib.pset)
    bars = box["AAA"]
    return TreeEvaluator(lib, bars.log_price, bars.log_return)(tree)


def test_terminals_and_operators_reproduce_the_strategy(frozen, fit_box):
    bars = fit_box["AAA"]
    toy = frozen[0].strategy
    entry, _ = toy.run(bars.log_price, bars.log_return)
    lib_a = build(resolve("s2a", frozen))
    np.testing.assert_array_equal(_evaluate(lib_a, fit_box, "S01Entry_v1"), entry)
    lib_b = build(resolve("s2b", frozen))
    lib_c = build(resolve("s2c", frozen))
    trend_b = _evaluate(lib_b, fit_box, "Gt_v1(S01Trend_v1, S01Gap_v1)")
    trend_c = _evaluate(
        lib_c, fit_box, "Gt_v1(S01Trend_v1(Ret_v1, Window_20), S01Gap_v1(LogPrice_v1, Window_40))"
    )
    np.testing.assert_array_equal(trend_b, trend_c)  # 2c at the defaults equals 2b


def test_arm1_selects_the_best_validation_fitness(frozen, fit_box, val_box):
    chosen = selection.select(frozen, fit_box, val_box, COSTS, FitnessConfig())
    assert set(chosen) == set(INSTRUMENTS)
    for name, result in chosen.items():
        best = max(result["validation"].values())
        assert result["validation"][result["selected"]] == best, name
    assert chosen == selection.select(frozen, fit_box, val_box, COSTS, FitnessConfig())


def test_frozen_registry_round_trip_and_tamper_detection(tmp_path):
    root = tmp_path / "generated" / "spectral"
    root.mkdir(parents=True)
    path = root / "s01__v1.py"
    path.write_text((FIXTURES / "toy_reversal.py").read_text())
    lock = tmp_path / "lock.toml"
    entry = {"sha256": registry.file_hash(path), "file": "spectral/s01__v1.py"}
    registry.write_lock({"s01": {**entry, "provenance": vars(TEST_PROVENANCE)}}, lock)
    (loaded,) = registry.load_frozen(tmp_path / "generated", lock)
    assert loaded.sid == "s01"
    assert loaded.strategy.name == "toy_reversal"
    assert loaded.provenance == TEST_PROVENANCE
    path.write_text(path.read_text() + "\n# edited\n")
    with pytest.raises(registry.LockMismatchError):
        registry.load_frozen(tmp_path / "generated", lock)


def test_period_is_the_gp_fixture_period():
    assert PERIOD.id == "P01"
    assert TINY.population == 16


def test_minimum_activity_scores_too_few_entries_as_no_trade():
    from datetime import date

    import pandas as pd

    from lpstgp.backtest.costs import CostModel
    from lpstgp.gp.fitness import market_part, prepare

    dates = pd.bdate_range("2004-01-01", "2006-12-31").to_numpy().astype("datetime64[D]")
    rng = np.random.default_rng(0)
    lr = rng.normal(3e-4, 0.01, len(dates))
    data = prepare(dates, lr, "business", (date(2005, 1, 1), date(2007, 1, 1)), CostModel(1, 1), 6)
    one_trade_entry, one_trade_exit = np.zeros(len(dates)), np.zeros(len(dates))
    one_trade_entry[data.active_from + 10] = 1.0
    one_trade_exit[data.active_from + 300] = 1.0
    strict = FitnessConfig(min_entries_per_year=2.0)
    value, parts = market_part(one_trade_entry, one_trade_exit, data, strict)
    assert value == strict.no_trade_value
    assert parts["required_trades"] == 4
    lenient = FitnessConfig(min_entries_per_year=0.0)  # the rule switched off
    lenient_value, _ = market_part(one_trade_entry, one_trade_exit, data, lenient)
    assert lenient_value != lenient.no_trade_value
    busy_entry = (np.arange(len(dates)) % 40 == 0).astype(float)
    busy_exit = (np.arange(len(dates)) % 40 == 20).astype(float)
    assert market_part(busy_entry, busy_exit, data, strict)[0] != strict.no_trade_value
