"""Briefs carry no names, dates or prices; seeds are paired across arms; seeded GP runs; and one
real-data cycle of every arm with the scripted session (protocol_wp3 §7)."""

import json
import random
import re
import shutil

import pytest
from tests.maintenance.conftest import problem_for

from lpstgp.config import load_paths
from lpstgp.gp import run as gprun
from lpstgp.gp.generate import Generator
from lpstgp.gp.run import GPConfig
from lpstgp.gp.variation import Limits, Rule
from lpstgp.maintenance import cycle, evidence, session, stub
from lpstgp.maintenance.cycle import ArmState
from lpstgp.types import Bool

CANARIES = ("SPX", "EURUSD", "GOLD", "CANARYXYZ")


def fake_records(lib, n_runs=6):
    """Run-record-shaped dicts with canary instrument names and dates in every field."""
    gen = Generator(lib, 504, random.Random(2))
    recs = []
    for k in range(n_runs):
        inst = CANARIES[k % len(CANARIES)]
        hall = []
        for rank in range(3):
            rule = Rule(gen.ramped(Bool, 2, 4), gen.ramped(Bool, 2, 4))
            hall.append(
                {
                    "rank": rank,
                    "entry": lib.to_names(rule.entry),
                    "exit": lib.to_names(rule.exit),
                    "entry_str": str(rule.entry),
                    "exit_str": str(rule.exit),
                    "fit": {"fitness": 0.5 - rank / 10, "instruments": {inst: {"no_trade": False}}},
                    "validation": {"fitness": 9.876},
                }
            )
        recs.append(
            {
                "instruments": [inst],
                "period": {"id": "PL1", "fit_start": "2003-07-01"},
                "seed": k,
                "selected": 0,
                "hall_of_fame": hall,
                "generations": [{"best_usage": hall[0]["entry"]} for _ in range(3)],
                "knockouts": [],
                "operator_seconds": {},
            }
        )
    return recs


@pytest.mark.parametrize("arm", cycle.ARMS)
def test_brief_has_no_instrument_names_dates_or_validation_figures(arm, arm3_lib):
    recs = fake_records(arm3_lib)
    asset = dict.fromkeys(CANARIES, "equity_index")
    names = evidence.gp_names(arm3_lib.operators.values())
    rows = evidence.operator_rows(recs, names)
    brief = session.render(
        arm, arm3_lib, rows, {}, evidence.summary(recs), evidence.elite_rules(recs, asset),
        {"status": "rejected", "what": "patch", "reason": cycle.REJECTED_BY_GATE},
        asset, 3, GPConfig(population=250, limits=Limits(17, 120, 504)),
    )  # fmt: skip
    for word in CANARIES:
        assert not re.search(rf"\b{word}\b", brief), word
    assert not re.search(r"\b(19|20)\d\d\b", brief), "a year or date"
    assert "9.876" not in brief  # validation figures never reach the LLM (D-071)
    assert "$" not in brief
    assert "lpstgp" not in brief.lower()
    assert "held-out data were clearly worse" in brief


def test_seeds_are_paired_across_arms_states_and_cycles():
    loop = cycle.Cycle.__new__(cycle.Cycle)
    loop.instruments, loop.runs, loop.campaign = ("SPX", "GOLD"), 3, "t"
    loop.gp_cfg = loop.fit_cfg = None
    loop.spec_digest = "s"
    a = loop.tasks("PL1", ArmState("aaaa"))
    b = loop.tasks("PL1", ArmState("bbbb", (("x", "y"),)))
    assert [t.seed for t in a] == [t.seed for t in b]
    assert [t.instruments for t in a] == [t.instruments for t in b]
    assert all(t.knockouts for t in a)
    assert b[0].seed_rules == (("x", "y"),)
    assert a[0].library == "state:aaaa"
    assert ArmState("aaaa").batch_key != ArmState("aaaa", (("x", "y"),)).batch_key


def test_seeded_rules_open_the_initial_population(arm3_lib, fit_box):
    gen = Generator(arm3_lib, 504, random.Random(9))
    seeds = [Rule(gen.ramped(Bool, 2, 4), gen.ramped(Bool, 2, 4)) for _ in range(3)]
    cfg = GPConfig(population=20, generations=1, limits=Limits(17, 120, 504), checkpoint_every=0)
    pop = gprun._initial(arm3_lib, Generator(arm3_lib, 504, random.Random(1)), cfg, seeds)
    assert [r.key() for r in pop[:3]] == [r.key() for r in seeds]
    assert len(pop) == 20
    assert len({r.key() for r in pop}) == 20
    problem = problem_for(arm3_lib, fit_box)
    plain = gprun.run_gp(arm3_lib, problem, None, cfg, 4)
    again = gprun.run_gp(arm3_lib, problem, None, cfg, 4, seeded=())
    assert plain["hall_of_fame"] == again["hall_of_fame"]
    assert all("best_usage" in g for g in plain["generations"])


def test_stub_session_proposes_the_briefs_elite_rules():
    brief = "1. (x, training fitness 1.0)\n   entry: `A(b)`\n   exit: `C(d)`\n"
    assert stub.ELITE.findall(brief) == [("A(b)", "C(d)")]


@pytest.mark.realdata
@pytest.mark.slow
def test_one_cycle_of_every_arm_on_real_training_data():
    campaign = "pytest-mechanics"
    paths = load_paths()
    root = paths.results_dir / "wp3" / "maintenance" / campaign
    runs = paths.results_dir / "tierA" / f"wp3-maintenance-{campaign}"
    for p in (root, runs):
        shutil.rmtree(p, ignore_errors=True)
    try:
        loop = cycle.Cycle(
            campaign, ("PL1",), instruments=("SPX", "EURUSD"), runs=1, cycles=1, workers=2,
            gp_overrides={"population": 20, "generations": 2}, session_runner=stub.run,
        )  # fmt: skip
        for arm in cycle.ARMS:
            (c,) = loop.run_arm(arm)
            assert c["decision"]["status"] in ("admitted", "rejected"), c["decision"]
            assert c["gate"]["pairs"] == 2
            lineage = json.loads((root / arm / "PL1" / "lineage.json").read_text())
            assert lineage["cycles"][0]["state_in"] == c["state_in"]["state_id"]
            for rec in runs.glob("*.json"):
                record = json.loads(rec.read_text())
                access = record["sandbox_access"]
                assert {a["stage"] for a in access} == {"fit", "validate"}
                assert max(a["horizon"] for a in access) <= record["period"]["test_start"]
        first = [loop.cycle_record(a, "PL1", 1)["batch_in"] for a in cycle.ARMS]
        assert len(set(first)) == 1  # every arm's first batch is the same (shared) one
    finally:
        for p in (root, runs):
            shutil.rmtree(p, ignore_errors=True)
