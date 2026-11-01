"""Prefix invariance across stages for every GP library, and an end-to-end poisoned-future canary.

Each stage's data are a prefix of the next stage's (FIT ⊂ VALIDATE ⊂ TEST), so a causal tree's
signal on an earlier stage must equal the start of its signal on a later one, whichever library it
comes from. The canary changes every bar from the VALIDATE horizon onwards and checks that a whole
GP run (search and validation selection) and arm-1 selection are unchanged.
"""

from __future__ import annotations

import random
import shutil

import numpy as np
import pandas as pd
import pytest
from tests.gp.conftest import INSTRUMENTS, LMAX, PERIOD, write_synthetic_tier

from lpstgp.backtest.costs import from_meta
from lpstgp.data import schema
from lpstgp.data.store import DataStore
from lpstgp.gp.evaluate import TreeEvaluator
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.generate import Generator
from lpstgp.gp.pset import build
from lpstgp.gp.run import GPConfig, Problem, run_gp
from lpstgp.libraries import resolve
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage
from lpstgp.strategies import selection
from lpstgp.strategies.registry import load_frozen
from lpstgp.types import Bool

LIBRARIES = ("seed", "technical", "s2a", "s2b", "s2c")


@pytest.fixture(scope="module")
def tier_dir(tmp_path_factory):
    return write_synthetic_tier(tmp_path_factory.mktemp("tier"))


@pytest.fixture(scope="module")
def boxes(tier_dir):
    store = DataStore(tier_dir)
    return {
        stage: Sandbox._open(store, PERIOD, stage, INSTRUMENTS, LMAX)  # synthetic data only
        for stage in (Stage.FIT, Stage.VALIDATE, Stage.TEST)
    }


def _reachable(lib, gen) -> set[str]:
    """Operators and data terminals that can appear in a rule (a Bool-rooted tree)."""
    types, frontier = {Bool}, [Bool]
    while frontier:
        for choice in gen.choices.get(frontier.pop(), []):
            for t in choice.spec.inputs:
                if t not in types:
                    types.add(t)
                    frontier.append(t)
    ops = {c.node.name for t in types for c in gen.choices.get(t, [])}
    return ops | {n.name for t in types for n in gen.terminals.get(t, [])}


def _covering_trees(lib, seed: int = 7, max_draws: int = 2000) -> list:
    """Random trees, kept while they add a primitive, until every reachable one is covered."""
    gen = Generator(lib, LMAX, random.Random(seed))
    wanted, seen, trees = _reachable(lib, gen), set(), []
    for _ in range(max_draws):
        tree = gen.ramped(Bool, 2, 6)
        new = {n.name for n in tree} & wanted - seen
        if new:
            trees.append(tree)
            seen |= new
        if seen == wanted:
            return trees
    raise AssertionError(f"not covered: {sorted(wanted - seen)}")


@pytest.mark.parametrize("library", LIBRARIES)
def test_every_library_is_prefix_invariant_from_fit_to_validate_to_test(boxes, library):
    """Every reachable operator and terminal of the library appears in at least one tree."""
    lib = build(resolve(library))
    trees = _covering_trees(lib)
    for name in INSTRUMENTS:
        signals = {}
        for stage, box in boxes.items():
            bars = box[name]
            ev = TreeEvaluator(lib, bars.log_price, bars.log_return)
            signals[stage] = [ev(t) for t in trees]
        for earlier, later in ((Stage.FIT, Stage.VALIDATE), (Stage.VALIDATE, Stage.TEST)):
            for a, b in zip(signals[earlier], signals[later], strict=True):
                np.testing.assert_array_equal(a, b[: len(a)], err_msg=f"{library} {name}")


def _poisoned_copy(tier_dir, tmp_path):
    """The synthetic tier with every price on or after the VALIDATE horizon scrambled."""
    out = tmp_path / "poisoned"
    shutil.copytree(tier_dir, out)
    horizon = pd.Timestamp(PERIOD.horizon(Stage.VALIDATE))
    rng = np.random.default_rng(99)
    for path in sorted((out / "processed").glob("*.parquet")):
        meta, frame = schema.read_meta(path), schema.read_frame(path)
        dates = pd.to_datetime(frame["date"])
        late = np.asarray(dates >= horizon)
        assert late.any(), "the synthetic tier must extend past the VALIDATE horizon"
        frame = pd.DataFrame({"date": dates, "close": frame["close"].to_numpy(copy=True)})
        frame.loc[late, "close"] *= rng.uniform(0.5, 1.5, late.sum())
        bars, _ = schema.normalise(frame)
        schema.write_parquet(bars, meta, path)
    return out


def _gp_record(store, library="seed"):
    fit_box = Sandbox.open(store, PERIOD, Stage.FIT, INSTRUMENTS, LMAX)
    val_box = Sandbox.open(store, PERIOD, Stage.VALIDATE, INSTRUMENTS, LMAX)
    lib = build(resolve(library))
    costs = {n: from_meta(fit_box[n].meta) for n in INSTRUMENTS}
    cfg = FitnessConfig()
    gp = GPConfig(population=12, generations=2, elitism=1, hof_size=3, cache_bytes=2**24)
    fit_p = Problem(lib, fit_box.bars, PERIOD.scored_window(Stage.FIT), costs, cfg, gp.cache_bytes)
    val_p = Problem(
        lib, val_box.bars, PERIOD.scored_window(Stage.VALIDATE), costs, cfg, gp.cache_bytes
    )
    summary = run_gp(lib, fit_p, val_p, gp, 5)
    chosen = selection.select(load_frozen(), fit_box, val_box, costs, cfg)
    return summary["hall_of_fame"], summary["selected"], chosen


@pytest.mark.parametrize("library", LIBRARIES)
def test_poisoned_future_changes_neither_a_gp_run_nor_arm_1(tier_dir, tmp_path, library):
    poisoned = _poisoned_copy(tier_dir, tmp_path)
    after = [
        Sandbox._open(DataStore(d), PERIOD, Stage.TEST, INSTRUMENTS, LMAX)["AAA"].close
        for d in (tier_dir, poisoned)
    ]
    assert not np.array_equal(*after)  # the poison is real: the future does differ
    clean = _gp_record(DataStore(tier_dir), library)
    dirty = _gp_record(DataStore(poisoned), library)
    assert clean == dirty
