"""End-to-end rehearsal of the WP2 pilot on synthetic instruments (D-052).

Runs the real driver (scripts/wp2_pilot.py) through every step — calibrate, budget-check,
go/no-go, freeze, a committed manifest and the one-time test read — at a tiny scale, in a
throwaway git repository with its own reports, results and synthetic Tier A data. Nothing in the
real repository, its reports or its trial register is touched.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.data import schema
from lpstgp.freeze import FreezeError
from lpstgp.gates.synthetic import garch_returns

PILOT = ("AAA", "BBB", "CCC")
CALIBRATION = ("AAA", "BBB")


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _synthetic_tier(root):
    dates = pd.bdate_range("2000-01-03", "2009-06-30")
    for k, name in enumerate(PILOT):
        r = garch_returns(len(dates), 300 + k)
        bars, _ = schema.normalise(
            pd.DataFrame({"date": dates, "close": 100 * np.exp(np.cumsum(r))})
        )
        meta = {
            "schema_version": 1, "instrument_id": name, "tier": "A",
            "asset_class": "equity_index", "calendar": "business", "source": "synthetic",
            "source_symbol": name, "close_only": True, "vendor_split_adjusted": False,
            "raw_files": [], "cost_bps": 2.0,
        }  # fmt: skip
        schema.write_parquet(bars, meta, root / "processed" / f"{name}.parquet")


@pytest.fixture
def rehearsal(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    for part in ("src", "scripts", "config"):
        shutil.copytree(
            REPO_ROOT / part,
            repo / part,
            ignore=shutil.ignore_patterns("__pycache__", "paths.toml", "*.pyc"),
        )
    (repo / "reports" / "wp2").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "rehearsal@example.com")
    _git(repo, "config", "user.name", "rehearsal")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "code")
    _synthetic_tier(tmp_path / "data" / "tierA")
    paths_file = tmp_path / "paths.toml"
    paths_file.write_text(
        f'data_dir = "{tmp_path / "data"}"\nresults_dir = "{tmp_path / "results"}"\n'
        f'reports_dir = "{repo / "reports"}"\ncache_dir = "{tmp_path / "cache"}"\n'
    )
    monkeypatch.setenv("LPSTGP_PATHS", str(paths_file))  # inherited by the spawned workers
    spec = importlib.util.spec_from_file_location(
        "wp2_pilot_rehearsal", REPO_ROOT / "scripts" / "wp2_pilot.py"
    )
    driver = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = driver
    spec.loader.exec_module(driver)
    scale = {
        "REPO_ROOT": repo, "REPORTS": repo / "reports" / "wp2",
        "PILOT_INSTRUMENTS": PILOT, "CALIBRATION_INSTRUMENTS": CALIBRATION,
        "CAL_BUDGET": 64, "CAL_POPULATIONS": (8, 16), "CAL_TOURNAMENTS": (3,),
        "CAL_RUNS": 2, "BUDGET_RUNS": 1, "GONOGO_RUNS": 2,
    }  # fmt: skip
    for name, value in scale.items():
        monkeypatch.setattr(driver, name, value)
    yield driver, repo
    sys.modules.pop(spec.name, None)


@pytest.mark.slow
@pytest.mark.parametrize("variant", ["plain", "strict"])
def test_the_whole_pilot_runs_end_to_end_and_reads_the_test_years_once(
    rehearsal, monkeypatch, variant
):
    """``strict`` forces the other branches: lambda raised stepwise (then, if x4 is not enough,
    a recorded decision) and the unique-evaluation budget."""
    import functools

    driver, repo = rehearsal
    if variant == "strict":
        cal = driver.calibration
        monkeypatch.setattr(
            cal, "lambda_check", functools.partial(cal.lambda_check, max_turnover=1.0)
        )
        monkeypatch.setattr(cal, "budget_unit", functools.partial(cal.budget_unit, ratio=0.0))
    real_register = REPO_ROOT / "reports" / "configuration_register.csv"
    before = real_register.read_bytes() if real_register.exists() else None
    paths, settings = load_paths(), load_settings()
    reports = repo / "reports" / "wp2"

    driver.step_calibrate(paths, settings, 2, "all")
    assert driver.chosen_parameters()["population"] in (8, 16)

    driver.step_budget_check(paths, settings, 2, "all")
    check = json.loads((reports / "budget_check.json").read_text())
    assert check["status"] in ("resolved", "unresolved")
    if variant == "strict":
        assert [t["multiplier"] for t in check["lambda_trials"]][:2] == [1, 2]
        assert check["budget_unit"]["unit"] == "unique"
    if check["status"] == "unresolved":  # what a recorded decision would do
        (reports / "lambda_decision.json").write_text(
            json.dumps({"lambda_turnover_multiplier": 1, "decision": "D-999"})
        )

    driver.step_gonogo(paths, settings, 2, "all")
    driver.step_gonogo(paths, settings, 2, "report")  # every task complete and current

    with pytest.raises(FreezeError, match="not tracked"):  # no manifest yet
        driver.step_pilot_test(paths, settings)
    driver.step_freeze(paths, settings)
    manifest = json.loads((reports / "freeze_manifest.json").read_text())
    tasks = 2 * len(PILOT) * (1 + 5 * 2)  # periods x instruments x (arm 1 + 5 GP arms x runs)
    assert len(manifest["rules"]) == tasks
    if variant == "strict":  # every GP run either spent its unique budget or is reported
        shortfall = json.loads((reports / "unique_budget_shortfall.json").read_text())
        reported = {t for ids in shortfall.values() for t in ids}
        for plan_path in driver.gonogo_plans(paths):
            for r in driver.records(plan_path):
                if "budget" in r:
                    assert r["budget"]["unit"] == "unique"
                    assert r["budget"]["cap_reached"] or r["campaign"]["task_id"] in reported
    with pytest.raises(FreezeError, match="not tracked"):
        driver.step_pilot_test(paths, settings)  # written but not committed
    _git(repo, "add", "reports/wp2/freeze_manifest.json")
    _git(repo, "commit", "-q", "-m", "freeze")

    driver.step_pilot_test(paths, settings)
    result = json.loads((reports / "pilot_go_no_go.json").read_text())
    assert result["decision"] in ("GO", "NO-GO")
    assert set(result["pooled_sharpe"]) == {"1", "2a", "2b", "2c", "6", "TA", "BH"}
    for period, access in result["test_access"].items():
        assert {a["instrument"] for a in access} == set(PILOT)
        assert all(a["stage"] == "test" for a in access), period
    assert (reports / "pilot_test_claim.json").exists()
    (reports / "pilot_go_no_go.json").unlink()  # even with the result gone, the claim holds
    with pytest.raises(FreezeError, match="already been claimed"):
        driver.step_pilot_test(paths, settings)

    after = real_register.read_bytes() if real_register.exists() else None
    assert after == before  # the real trial register is untouched
