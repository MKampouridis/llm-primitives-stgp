"""WP4 periods: eligibility per period (counts only) and per-period instruments in the cycle."""

import json

import pytest

from lpstgp.config import REPO_ROOT, load_settings
from lpstgp.data import eligibility
from lpstgp.maintenance import cycle
from lpstgp.splits import all_periods

PERIODS = all_periods(load_settings())


def test_pc_is_assessed_without_its_test_year_and_the_others_unchanged():
    pc = eligibility.assessed(PERIODS["PC"])
    assert pc.test_end == pc.test_start == PERIODS["PC"].test_start
    assert eligibility.assessed(PERIODS["P05"]) == PERIODS["P05"]
    assert eligibility.WP4_PERIODS[-1] == "PC"
    assert len(eligibility.WP4_PERIODS) == 19


def test_committed_table_matches_wp1s_496_pairs():
    table = json.loads((REPO_ROOT / "reports" / "wp4" / "eligibility.json").read_text())
    assert table["primary_pairs"] == 496
    assert list(table["eligible"]) == list(eligibility.WP4_PERIODS)
    counts = [len(table["eligible"][f"P{k:02d}"]) for k in range(1, 19)]
    assert counts[0] == 25
    assert counts[-1] == 31
    assert counts == sorted(counts)  # instruments only enter


@pytest.mark.realdata
def test_eligibility_recomputes_to_the_committed_table():
    from lpstgp.config import load_paths

    table = json.loads((REPO_ROOT / "reports" / "wp4" / "eligibility.json").read_text())
    assert eligibility.table(load_paths(), load_settings()) == table["eligible"]


def test_cycle_tasks_use_each_periods_own_instruments():
    loop = cycle.Cycle.__new__(cycle.Cycle)
    loop.by_period = {"PL1": ("SPX",), "PL2": ("SPX", "GOLD")}
    loop.runs, loop.campaign, loop.spec_digest = 2, "t", "s"
    loop.gp_cfg = loop.fit_cfg = None
    assert {t.instruments for t in loop.tasks("PL1", cycle.ArmState("a"))} == {("SPX",)}
    assert len(loop.tasks("PL2", cycle.ArmState("a"))) == 4
