"""Knock-out evidence (FIT only) and the maintenance leakage tests (protocol_wp3 §7)."""

import ast
from dataclasses import replace
from pathlib import Path

import numpy as np
from tests.gp.conftest import INSTRUMENTS, LMAX, PERIOD
from tests.maintenance.conftest import cross_domain_rules, problem_for

from lpstgp.data.store import DataStore
from lpstgp.maintenance import knockout
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage

MAINTENANCE = Path(knockout.__file__).parent


def test_knockout_replaces_the_operator_by_its_median(arm3_lib, fit_box):
    problem = problem_for(arm3_lib, fit_box)
    rule = cross_domain_rules(arm3_lib, 1)[0]
    op = knockout.operators_in(rule, problem)
    target = next(o for o in op if arm3_lib.operators[o].domain != "core")
    ev = problem.evaluators["AAA"]
    d = problem.data["AAA"]
    ko = knockout.KnockoutEvaluator(ev, target, (d.active_from, d.stop))
    tree = rule.entry if any(n.name == target for n in rule.entry) else rule.exit
    i = next(k for k, n in enumerate(tree) if n.name == target)
    span = tree.searchSubtree(i)
    sub = type(tree)(tree[span])
    value = ko(sub)
    finite = value[np.isfinite(value)]
    assert finite.size
    assert np.all(finite == finite[0])
    true = ev(sub)[d.active_from : d.stop]
    assert finite[0] == np.median(true[np.isfinite(true)])


def test_knockouts_cover_only_the_targets_and_leave_the_run_cache_true(arm3_lib, fit_box):
    problem = problem_for(arm3_lib, fit_box)
    rules = cross_domain_rules(arm3_lib, 4)
    before = [problem.score(r).fitness for r in rules]
    targets = [n for n, s in arm3_lib.operators.items() if s.domain != "core"]
    out = knockout.contributions(problem, rules, targets)
    assert [o["fitness"] for o in out] == before
    for o in out:
        assert set(o["operators"]) <= set(targets)
        for cell in o["operators"].values():
            assert set(cell["delta_segment_sharpe"]) == set(INSTRUMENTS)
    assert [problem.score(r).fitness for r in rules] == before  # cache not polluted


def test_knockout_evidence_ignores_data_after_the_fit_window(arm3_lib, tier, fit_box):
    """Poisoned future: bars after the FIT window's end cannot change any knock-out figure."""
    rules = cross_domain_rules(arm3_lib, 3, seed=8)
    targets = [n for n, s in arm3_lib.operators.items() if s.domain != "core"]
    clean = knockout.contributions(problem_for(arm3_lib, fit_box), rules, targets)
    val_box = Sandbox.open(DataStore(tier), PERIOD, Stage.VALIDATE, INSTRUMENTS, LMAX)
    poisoned = {}
    for name, bars in val_box.bars.items():
        n_fit = len(fit_box[name].dates)
        lr = np.array(bars.log_return)
        lr[n_fit:] = np.where(np.arange(len(lr) - n_fit) % 2, 0.2, -0.2)  # wild future
        lp = np.array(bars.log_price)
        lp[n_fit:] = lp[n_fit - 1] + np.cumsum(lr[n_fit:])
        poisoned[name] = replace(bars, log_return=lr, log_price=lp)
    box = replace(val_box, bars=poisoned)
    problem = problem_for(arm3_lib, box)  # the FIT window, on series that run on past it
    assert knockout.contributions(problem, rules, targets) == clean


def test_maintenance_code_never_opens_the_test_stage():
    for path in MAINTENANCE.rglob("*.py"):
        text = path.read_text()
        tree = ast.parse(text)
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert "TEST" not in names, path.name
        assert "open_pilot_test" not in text, path.name
