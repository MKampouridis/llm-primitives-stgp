"""Tree evaluation, the tree -> signal pipeline across stages, and fitness."""

import random
from dataclasses import replace
from datetime import date

import numpy as np
import pytest
from tests.gp.conftest import INSTRUMENTS, PERIOD

from lpstgp.backtest.costs import CostModel
from lpstgp.gp import fitness as fit
from lpstgp.gp.evaluate import TreeEvaluator
from lpstgp.gp.generate import Generator
from lpstgp.gp.run import Problem
from lpstgp.gp.variation import Rule
from lpstgp.operators.registry import discover
from lpstgp.splits import Stage
from lpstgp.types import Bool

LENIENT = fit.FitnessConfig(execution_lag=1, min_entries_per_year=0.0)  # as written for WP1

OPS = {s.name: s for s in discover().operators.values()}
COSTS = {name: CostModel(2.0, 2.0) for name in INSTRUMENTS}


def test_evaluator_matches_direct_composition(seed_lib, fit_box):
    bars = fit_box["AAA"]
    ev = TreeEvaluator(seed_lib, bars.log_price, bars.log_return)
    names = [
        "ExceedsQuantile_v1",
        "ShannonEntropy_v1",
        "RollingHist_v1",
        "Ret_v1",
        "Window_20",
        "LongWindow_60",
        "Quantile_0p8",
    ]
    out = ev(seed_lib.from_names(names))
    expected = OPS["exceeds_quantile"](
        OPS["shannon_entropy"](OPS["rolling_hist"](np.array(bars.log_return), window=20)),
        window=60,
        q=0.8,
    )
    np.testing.assert_array_equal(out, expected)
    assert not out.flags.writeable
    hits = ev.cache.hits
    ev(seed_lib.from_names(names))
    assert ev.cache.hits == hits + 1  # the whole tree is served from the cache


def test_signals_are_prefix_invariant_across_stages(seed_lib, fit_box, val_box):
    """FIT data are a prefix of VALIDATE data, so every tree's FIT signal is a prefix of its VALIDATE signal."""
    gen = Generator(seed_lib, 504, random.Random(21))
    for name in INSTRUMENTS:
        f, v = fit_box[name], val_box[name]
        ev_fit = TreeEvaluator(seed_lib, f.log_price, f.log_return)
        ev_val = TreeEvaluator(seed_lib, v.log_price, v.log_return)
        for _ in range(25):
            tree = gen.ramped(Bool, 2, 5)
            a, b = ev_fit(tree), ev_val(tree)
            np.testing.assert_array_equal(a, b[: len(a)])


def test_segments_of_p01():
    bounds = fit.segment_bounds(PERIOD.fit_start, PERIOD.val_start, 6)
    assert bounds == [
        (date(2005, 7, 1), date(2006, 1, 1)),
        (date(2006, 1, 1), date(2006, 7, 1)),
        (date(2006, 7, 1), date(2007, 1, 1)),
        (date(2007, 1, 1), date(2007, 7, 1)),
    ]


@pytest.fixture
def problem(seed_lib, fit_box):
    return Problem(seed_lib, fit_box.bars, PERIOD.scored_window(Stage.FIT), COSTS, LENIENT, 2**26)


def constant_rule(lib, entry: bool, exit_: bool) -> Rule:
    """Rules built from comparisons of a series with itself: Gt(x, x) is always false."""
    x = ["MeanKsd_v1", "Ret_v1", "LongWindow_60", "KSigma_m2"]
    never = lib.from_names(["Gt_v1", *x, *x])
    always = lib.from_names(["Not_v1", "Gt_v1", *x, *x])
    return Rule(always if entry else never, always if exit_ else never)


def test_no_trade_rule_gets_the_floor(problem, seed_lib):
    score = problem.score(constant_rule(seed_lib, entry=False, exit_=False))
    assert score.fitness == pytest.approx(LENIENT.no_trade_value - 0.01 * score.components["size"])


def test_buy_and_hold_rule_scores_the_asset(problem, seed_lib, fit_box):
    score = problem.score(constant_rule(seed_lib, entry=True, exit_=False))
    comps = score.components["instruments"]["AAA"]
    assert comps["trades"] == 1
    assert comps["exposure"] > 0.99
    data = problem.data["AAA"]
    simple = np.expm1(np.asarray(fit_box["AAA"].log_return))
    for (lo, hi), s in zip(data.segments, comps["segment_sharpes"], strict=True):
        seg = simple[lo:hi].copy()
        if lo == data.active_from:
            seg[0] = 0.0  # entry at the first close: no return on the entry bar itself
        expected = seg.mean() / seg.std(ddof=1) * np.sqrt(252)
        assert s == pytest.approx(
            expected, abs=0.05
        )  # entry cost and the first bar differ slightly


def test_size_penalty_and_signal_hash(problem, seed_lib):
    a = problem.score(constant_rule(seed_lib, entry=True, exit_=False))
    cfg = replace(LENIENT, lambda_size=0.0)
    unpenalised = fit.score(
        problem.signals(constant_rule(seed_lib, True, False)),
        problem.data,
        a.components["size"],
        cfg,
    )
    assert unpenalised.fitness - a.fitness == pytest.approx(0.01 * a.components["size"])
    assert unpenalised.signal_hash == a.signal_hash


def test_rules_that_trade_identically_share_one_hall_of_fame_slot(problem, seed_lib):
    """Deduplication is by held positions (D-029, D-047), not by raw signals."""
    flat_a = constant_rule(seed_lib, entry=False, exit_=False)
    flat_b = constant_rule(seed_lib, entry=False, exit_=True)  # other exit values, still flat
    a, b = problem.score(flat_a), problem.score(flat_b)
    assert flat_a.key() != flat_b.key()
    assert a.signal_hash == b.signal_hash
    held = problem.score(constant_rule(seed_lib, entry=True, exit_=False))
    assert held.signal_hash != a.signal_hash
