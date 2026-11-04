"""GP development E1 (D-090): cells, configurations and the pre-registered pass marks."""

import sys

import numpy as np

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
