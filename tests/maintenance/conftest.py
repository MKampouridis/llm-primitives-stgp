"""Synthetic data and the arm-3 library for the maintenance tests (no real data needed)."""

from __future__ import annotations

import random

import pytest
from tests.gp.conftest import INSTRUMENTS, LMAX, PERIOD, write_synthetic_tier

from lpstgp import libraries
from lpstgp.backtest.costs import CostModel
from lpstgp.data.store import DataStore
from lpstgp.gp import fitness as fit
from lpstgp.gp.generate import Generator
from lpstgp.gp.pset import build
from lpstgp.gp.run import Problem
from lpstgp.gp.variation import Rule
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage
from lpstgp.types import Bool

LENIENT = fit.FitnessConfig(execution_lag=1, min_entries_per_year=0.0)
COSTS = {name: CostModel(2.0, 2.0) for name in INSTRUMENTS}


@pytest.fixture(scope="session")
def arm3_lib():
    return build(libraries.resolve("arm3"))


@pytest.fixture(scope="session")
def tier(tmp_path_factory):
    return write_synthetic_tier(tmp_path_factory.mktemp("tier"))


@pytest.fixture(scope="session")
def fit_box(tier):
    return Sandbox.open(DataStore(tier), PERIOD, Stage.FIT, INSTRUMENTS, LMAX)


def problem_for(lib, box) -> Problem:
    return Problem(lib, box.bars, PERIOD.scored_window(Stage.FIT), COSTS, LENIENT, 2**26)


def cross_domain_rules(lib, n: int, seed: int = 3) -> list[Rule]:
    """Random valid rules that use at least one cross-domain operator."""
    gen = Generator(lib, LMAX, random.Random(seed))
    out = []
    while len(out) < n:
        rule = Rule(gen.ramped(Bool, 2, 4), gen.ramped(Bool, 2, 4))
        names = {node.name for tree in rule.trees() for node in tree}
        if any(lib.operators[x].domain != "core" for x in names if x in lib.operators):
            out.append(rule)
    return out
