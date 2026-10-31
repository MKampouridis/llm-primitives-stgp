"""Pilot test evaluation end to end on synthetic data: freeze, gated test read, go/no-go."""

import subprocess

import numpy as np
import pytest
from tests.gp.conftest import INSTRUMENTS, write_synthetic_tier

from lpstgp import pilot
from lpstgp.backtest.costs import CostModel
from lpstgp.config import load_settings
from lpstgp.data.store import DataStore
from lpstgp.freeze import FreezeError, FreezeManifest, write_manifest
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.pset import build
from lpstgp.gp.run import GPConfig, Problem, run_gp
from lpstgp.libraries import resolve
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, pilot_periods

SETTINGS = load_settings()
PL1, PL2 = pilot_periods(SETTINGS)
CFG = FitnessConfig(execution_lag=2, min_entries_per_year=0.0)
TINY = GPConfig(population=12, generations=2, elitism=2, hof_size=3, cache_bytes=2**25)


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    root = write_synthetic_tier(tmp_path_factory.mktemp("tier"))
    return DataStore(root, max_horizon=SETTINGS["leakage"]["max_horizon"])


@pytest.fixture(scope="module")
def record(store):
    lib = build(resolve("technical"))
    costs = {n: CostModel(2.0, 2.0) for n in INSTRUMENTS}
    boxes = {s: Sandbox.open(store, PL1, s, INSTRUMENTS, 504) for s in (Stage.FIT, Stage.VALIDATE)}
    fit = Problem(lib, boxes[Stage.FIT].bars, PL1.scored_window(Stage.FIT), costs, CFG, 2**25)
    val = Problem(
        lib, boxes[Stage.VALIDATE].bars, PL1.scored_window(Stage.VALIDATE), costs, CFG, 2**25
    )
    summary = run_gp(lib, fit, val, TINY, seed=1)
    return {
        "campaign": {"task_id": "ta/PL1/AAA+BBB/r01"},
        "library": {"name": "technical"},
        **summary,
    }


def _commit(repo, path):
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "t@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "t"], check=True)
    subprocess.run([*git, "add", path.name], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "freeze"], check=True)


def test_frozen_rule_is_evaluated_on_the_test_year_only_after_a_committed_freeze(
    store, record, tmp_path
):
    rules = pilot.manifest_rules([record])
    assert set(rules) == {"ta/PL1/AAA+BBB/r01"}
    path = tmp_path / "freeze.json"
    write_manifest(path, rules, {"settings": "x"})
    with pytest.raises(FreezeError):
        FreezeManifest.load_committed(path, repo=tmp_path)  # not committed yet
    _commit(tmp_path, path)
    manifest = FreezeManifest.load_committed(path, repo=tmp_path)
    manifest.require("ta/PL1/AAA+BBB/r01", pilot.rule_hash(record))
    box = Sandbox.open_pilot_test(
        store, PL1, INSTRUMENTS, 504, pilot_periods=pilot_periods(SETTINGS), manifest=manifest
    )
    series = pilot.evaluate_on_test(record, box, CFG)
    for name, (dates, net) in series.items():
        assert dates.min() >= np.datetime64(PL1.test_start), name
        assert dates.max() < np.datetime64(PL1.test_end)
        assert np.isfinite(net).all()
    again = pilot.evaluate_on_test(record, box, CFG)
    for name in series:
        np.testing.assert_array_equal(series[name][1], again[name][1])
    hold = pilot.buy_and_hold(box, CFG)
    assert set(hold) == set(INSTRUMENTS)


def test_go_no_go_rule_and_comparisons():
    rng = np.random.default_rng(3)
    dates = np.arange(np.datetime64("2006-07-03"), np.datetime64("2008-06-30"))
    base = rng.normal(2e-4, 0.01, len(dates))
    pooled = {"1": (dates, base), "2c": (dates, base + rng.normal(0, 1e-3, len(dates)))}
    out = pilot.go_no_go(pooled, {"PL1": pooled}, resamples=200)
    assert out["decision"] == "GO"
    assert "2c - 1" in out["comparisons"]
    worse = {"1": (dates, base), "2c": (dates, base - 0.002)}
    assert pilot.go_no_go(worse, {"PL1": worse}, resamples=200)["decision"] == "NO-GO"
