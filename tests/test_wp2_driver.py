"""The WP2 driver's guards (scripts/wp2_pilot.py): the go/no-go never runs on unresolved weights."""

import importlib.util
import json
import sys

import pytest

from lpstgp.config import REPO_ROOT, load_settings


@pytest.fixture
def driver(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "wp2_pilot", REPO_ROOT / "scripts" / "wp2_pilot.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["wp2_pilot"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPORTS", tmp_path)
    choice = {
        "population": 500,
        "tournament": 3,
        "generations": 60,
        "requested_evaluations": 30_500,
    }
    choice["provenance"] = module.provenance(load_settings(), [])
    (tmp_path / "calibration.json").write_text(json.dumps(choice))
    module._test_choice = choice
    return module


def _budget(tmp_path, multiplier, base=None, unit="requested", status=None, driver=None):
    import wp2_pilot as driver_module  # the fixture's module, registered below

    driver = driver or driver_module
    base = load_settings()["fitness"]["lambda_turnover"] if base is None else base
    status = status or ("resolved" if multiplier else "unresolved")
    (tmp_path / "budget_check.json").write_text(
        json.dumps({"status": status, "budget_unit": {"unit": unit},
                    "lambda_turnover_multiplier": multiplier, "base_lambda_turnover": base,
                    "calibration_digest": driver.digest(driver._test_choice),
                    "provenance": driver.provenance(load_settings(), [])})
    )  # fmt: skip


def test_gonogo_applies_the_chosen_lambda_to_every_arm(driver, tmp_path):
    base = load_settings()["fitness"]["lambda_turnover"]
    _budget(tmp_path, 2)
    configs = driver.gonogo_configs()
    assert {c.name for c in configs} == {"arm1", "arm2a", "arm2b", "arm2c", "arm6", "armTA"}
    assert all(c.fitness == {"lambda_turnover": 2 * base} for c in configs)
    _budget(tmp_path, 1)
    assert all(c.fitness == {} for c in driver.gonogo_configs())


def test_gonogo_refuses_unresolved_or_moved_lambda(driver, tmp_path):
    _budget(tmp_path, None)
    with pytest.raises(SystemExit, match="unresolved"):
        driver.gonogo_configs()
    (tmp_path / "lambda_decision.json").write_text(json.dumps({"lambda_turnover_multiplier": 4}))
    with pytest.raises(SystemExit, match="name the decision"):
        driver.gonogo_configs()
    (tmp_path / "lambda_decision.json").write_text(
        json.dumps({"lambda_turnover_multiplier": 4, "decision": "D-099"})
    )
    assert driver.gonogo_configs()[1].fitness["lambda_turnover"] > 0
    _budget(tmp_path, 2, base=0.123)  # the settings' base lambda was edited after the check
    with pytest.raises(SystemExit, match="keep the base value"):
        driver.gonogo_configs()


def test_unique_budget_has_a_ceiling(driver, tmp_path):
    _budget(tmp_path, 1, unit="unique")
    gp = driver.gonogo_configs()[1].gp
    assert gp["budget_unit"] == "unique"
    assert gp["max_unique_evaluations"] == 30_500
    assert gp["generations"] == driver.UNIQUE_CEILING * 60


def test_gonogo_refuses_pending_stale_or_foreign_reports(driver, tmp_path, monkeypatch):
    _budget(tmp_path, None, status="pending")
    (tmp_path / "lambda_decision.json").write_text(
        json.dumps({"lambda_turnover_multiplier": 2, "decision": "D-099"})
    )
    with pytest.raises(SystemExit, match="under way"):  # a pending check is never overridden
        driver.gonogo_configs()
    _budget(tmp_path, 2)
    other = {**driver._test_choice, "population": 250}  # calibration rerun after the check
    (tmp_path / "calibration.json").write_text(json.dumps(other))
    with pytest.raises(SystemExit, match="another calibration"):
        driver.gonogo_configs()
    monkeypatch.setattr(driver, "source_digest", lambda: "edited")
    with pytest.raises(SystemExit, match="stale"):
        driver.gonogo_configs()
