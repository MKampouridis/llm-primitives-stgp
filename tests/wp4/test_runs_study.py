"""The §6.4 runs-per-configuration rule (WP4 M2)."""

import random

import pytest

from lpstgp import runs_study


def _cells(spread: float, n_cells: int = 4) -> dict:
    rng = random.Random(1)
    return {
        (f"I{k}", "PL1"): [rng.gauss(1.0, spread) for _ in range(runs_study.RUNS)]
        for k in range(n_cells)
    }


def test_low_spread_keeps_30_runs_and_high_spread_needs_50():
    assert runs_study.decide(_cells(0.05), draws=300)["runs_per_configuration"] == 30
    assert runs_study.decide(_cells(1.0), draws=300)["runs_per_configuration"] == 50


def test_decision_is_reproducible_and_needs_exactly_100_runs():
    cells = _cells(0.3)
    assert runs_study.decide(cells, draws=200) == runs_study.decide(cells, draws=200)
    short = {("I0", "PL1"): [1.0] * 99}
    with pytest.raises(ValueError, match="99 runs"):
        runs_study.decide(short)


def test_validation_sharpe_reads_the_selected_rules_own_instrument():
    record = {
        "instruments": ["SPX"],
        "period": {"id": "PL1"},
        "selected": 1,
        "hall_of_fame": [
            {"validation": {"instruments": {"SPX": {"sharpe": 9.0}}}},
            {"validation": {"instruments": {"SPX": {"sharpe": 0.7}}}},
        ],
    }
    assert runs_study.validation_sharpe(record) == 0.7
    assert runs_study.cells([record]) == {("SPX", "PL1"): [0.7]}
