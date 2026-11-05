"""GP development E1 (D-090): cells, configurations and the pre-registered pass marks."""

import sys

import numpy as np
import pytest

from lpstgp.config import REPO_ROOT, load_settings

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gp_dev


def _rows(gain, rho_sign, config="e1-2c-lcb", data="pooled", cells=12, runs=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(cells):
        fit = rng.normal(1, 0.3, runs)
        val = rho_sign * fit + rng.normal(0, 0.1, runs)
        for f, v in zip(fit, val, strict=True):
            rows.append({"config": config, "data": data, "cell": (str(c), "PL1"),
                         "fit_score": f, "fit_sharpe": f, "val_sharpe": v,
                         "val_gen0": 0.5, "val_last": 0.5 + gain + rng.normal(0, 0.02),
                         "trades_fit": 10, "exposure_fit": 0.5, "exposure_val": 0.5})  # fmt: skip
    return rows


def test_pass_marks_need_both_an_evolution_gain_and_predictive_training_scores():
    good = gp_dev.e1_summary(_rows(0.3, +1))["e1-2c-lcb/pooled"]
    assert good["passes"]
    no_gain = gp_dev.e1_summary(_rows(0.0, +1))["e1-2c-lcb/pooled"]
    assert not no_gain["pass_gain"]
    assert not no_gain["passes"]
    unpredictive = gp_dev.e1_summary(_rows(0.3, -1))["e1-2c-lcb/pooled"]
    assert unpredictive["pass_gain"]
    assert not unpredictive["passes"]
    report = gp_dev.e1_report(gp_dev.e1_summary(_rows(0.3, +1)))
    assert "go to E2 with e1-2c-lcb/pooled" in report
    assert "stop and rethink" in gp_dev.e1_report(gp_dev.e1_summary(_rows(0.0, +1)))


def test_cells_use_only_validation_years_before_wp4s_first_test_year():
    from lpstgp.splits import all_periods

    periods = all_periods(load_settings())
    cells = gp_dev.e1_cells()
    assert {p for _, p in cells} == {"PL1", "PL2", "P01"}
    # the VALIDATE horizon is the test start: no read reaches 2008-07-01, P01's test year
    assert max(periods[p].test_start for _, p in cells).isoformat() == "2008-07-01"
    pooled = [i for i, _ in cells if len(i) > 1]
    assert len(pooled) == 10
    assert all(len(set(i)) == len(i) for i in pooled)
    names = [c.name for c in gp_dev.e1_configs(load_settings())]
    assert names == ["e1-2c-comp", "e1-2c-lcb", "e1-TA-comp", "e1-TA-lcb"]


def test_e2_configurations_and_the_benchmark_mark():
    configs = gp_dev.e2_configs(load_settings())
    assert [c.name for c in configs] == ["e2-2c", "e2-TA"]
    assert all(dict(c.fitness) == {"position_mode": "reverse", "vol_target": 0.10} for c in configs)
    rows = [{"config": "e2-2c", "cell": ("A+B", "G1"), "val_sharpe": v} for v in (0.9, 1.0, 1.1)]
    rows += [{"config": "e2-2c", "cell": ("C+D", "G3"), "val_sharpe": v} for v in (0.2, 0.3)]
    bench = {("A+B", "G1"): {"trend": 0.8, "hold": 1.2}, ("C+D", "G3"): {"trend": 0.5, "hold": 0.0}}
    got = gp_dev.e2_compare(rows, bench)["e2-2c"]
    assert got["vs_trend"] == pytest.approx(np.median([0.2, -0.25]))
    assert got["pass_benchmark"] is False  # -0.025 < 0


def test_the_gate_bar_is_the_expected_maximum_of_null_sharpe_ratios():
    rng = np.random.default_rng(0)
    n, bars = 500, 1500
    maxima = [max(rng.normal(0, 1 / np.sqrt(bars), n)) * np.sqrt(252) for _ in range(300)]
    assert gp_dev.expected_max_sharpe(n, bars, 252) == pytest.approx(np.mean(maxima), rel=0.08)
    assert gp_dev.expected_max_sharpe(1, bars, 252) == 0.0
    assert gp_dev.expected_max_sharpe(5000, bars, 252) > gp_dev.expected_max_sharpe(50, bars, 252)


def test_e4_decision_needs_a_positive_median_and_a_holm_adjusted_p():
    cells = {str(k): {"trend": 0.5, "free": 0.5 + 0.1 * (k + 1), "gated": 0.5,
                      "ensemble": 0.5 - 0.05, "gated_ensemble": 0.5 + 0.01 * (-1) ** k}
             for k in range(14)}  # fmt: skip
    d = gp_dev.e4_decision(cells)
    assert d["free"]["beats_trend"]
    assert d["free"]["p_holm"] >= d["free"]["p"]
    assert not d["gated"]["beats_trend"]
    assert d["gated"]["non_inferior"]
    assert not d["ensemble"]["beats_trend"]
    assert d["ensemble"]["non_inferior"]
    assert not d["gated_ensemble"]["beats_trend"]
