"""A tiny STGP run on synthetic sandboxes: structure, budget accounting and reproducibility."""

import json
import subprocess
import sys

import pytest
from tests.gp.conftest import INSTRUMENTS, PERIOD

from lpstgp.backtest.costs import CostModel
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.run import GPConfig, Problem, run_gp
from lpstgp.splits import Stage

TINY = GPConfig(population=16, generations=2, elitism=2, hof_size=4, cache_bytes=2**26)
COSTS = {name: CostModel(2.0, 2.0) for name in INSTRUMENTS}


def tiny_run(lib, fit_box, val_box, seed, instruments=("AAA",)):
    fit_bars = {k: fit_box[k] for k in instruments}
    val_bars = {k: val_box[k] for k in instruments}
    fp = Problem(
        lib, fit_bars, PERIOD.scored_window(Stage.FIT), COSTS, FitnessConfig(), TINY.cache_bytes
    )
    vp = Problem(
        lib,
        val_bars,
        PERIOD.scored_window(Stage.VALIDATE),
        COSTS,
        FitnessConfig(),
        TINY.cache_bytes,
    )
    return run_gp(lib, fp, vp, TINY, seed)


def test_run_summary(seed_lib, fit_box, val_box):
    out = tiny_run(seed_lib, fit_box, val_box, seed=1)
    assert out["budget"]["requested_evaluations"] == TINY.population * (TINY.generations + 1)
    assert 0 < out["budget"]["unique_evaluations"] <= out["budget"]["requested_evaluations"]
    assert len(out["generations"]) == TINY.generations + 1
    assert 1 <= len(out["hall_of_fame"]) <= TINY.hof_size
    best = out["hall_of_fame"][out["selected"]]
    assert "validation" in best
    assert best["lookback"] <= 504
    assert json.loads(json.dumps(out, default=str))  # serialisable
    fits = [h["fit"]["fitness"] for h in out["hall_of_fame"]]
    assert fits == sorted(fits, reverse=True)


def test_same_seed_same_run_different_seed_different_run(seed_lib, fit_box, val_box):
    a = tiny_run(seed_lib, fit_box, val_box, seed=5)
    b = tiny_run(seed_lib, fit_box, val_box, seed=5)
    c = tiny_run(seed_lib, fit_box, val_box, seed=6)

    def keys(record):
        return [
            (h["entry_str"], h["exit_str"], h["fit"]["fitness"]) for h in record["hall_of_fame"]
        ]

    assert keys(a) == keys(b)
    assert [g["best"] for g in a["generations"]] == [g["best"] for g in b["generations"]]
    assert keys(a) != keys(c)


def test_pooled_fitness_over_two_instruments(seed_lib, fit_box, val_box):
    out = tiny_run(seed_lib, fit_box, val_box, seed=2, instruments=INSTRUMENTS)
    assert set(out["hall_of_fame"][0]["fit"]["instruments"]) == set(INSTRUMENTS)


SCRIPT = """
import json, sys
from pathlib import Path
from tests.gp.conftest import write_synthetic_tier, PERIOD, INSTRUMENTS, LMAX
from tests.gp.test_run import tiny_run
from lpstgp.data.store import DataStore
from lpstgp.gp.pset import build
from lpstgp.operators.registry import discover
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage
root = write_synthetic_tier(Path(sys.argv[1]))
fit_box = Sandbox.open(DataStore(root), PERIOD, Stage.FIT, INSTRUMENTS, LMAX)
val_box = Sandbox.open(DataStore(root), PERIOD, Stage.VALIDATE, INSTRUMENTS, LMAX)
out = tiny_run(build(discover().library("seed")), fit_box, val_box, seed=5)
print(json.dumps([(h["entry_str"], h["exit_str"], h["fit"]["fitness"]) for h in out["hall_of_fame"]]))
"""


@pytest.mark.slow
def test_seeded_run_is_reproducible_in_a_fresh_process(seed_lib, fit_box, val_box, tmp_path):
    env_out = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONHASHSEED": "999", "PATH": "", "PYTHONPATH": "."},
    )
    remote = [tuple(x) for x in json.loads(env_out.stdout.strip().splitlines()[-1])]
    local = [
        (h["entry_str"], h["exit_str"], h["fit"]["fitness"])
        for h in tiny_run(seed_lib, fit_box, val_box, 5)["hall_of_fame"]
    ]
    assert remote == local


def test_configs_from_settings():
    from lpstgp.config import load_settings
    from lpstgp.runner import configs_from_settings

    gp_cfg, fit_cfg = configs_from_settings(load_settings(), population=32)
    assert gp_cfg.population == 32
    assert gp_cfg.limits.lookback_max == 504
    assert fit_cfg.segment_months == 6


@pytest.mark.parametrize("cap", [10, 17, 40])
def test_unique_budget_is_matched_exactly_across_arms(
    seed_lib, conventional_lib, fit_box, val_box, cap
):
    """Under a unique budget every arm scores exactly the cap: no arm gets extra evaluations."""
    from dataclasses import replace

    cfg = replace(TINY, generations=50, budget_unit="unique", max_unique_evaluations=cap)
    for lib in (seed_lib, conventional_lib):
        fp = Problem(
            lib, {"AAA": fit_box["AAA"]}, PERIOD.scored_window(Stage.FIT), COSTS,
            FitnessConfig(), cfg.cache_bytes,
        )  # fmt: skip
        out = run_gp(lib, fp, None, cfg, 3)
        assert out["budget"]["unique_evaluations"] == cap
        assert out["budget"]["cap_reached"]
        assert out["budget"]["overshoot"] == 0
        assert all(m["fit"]["fitness"] > -1e9 for m in out["hall_of_fame"])  # only scored rules
