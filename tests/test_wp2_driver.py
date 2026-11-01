"""The WP2 driver's guards (scripts/wp2_pilot.py): the go/no-go never runs on unresolved weights."""

import importlib.util
import json

import pytest

from lpstgp.config import REPO_ROOT, load_settings


@pytest.fixture
def driver(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "wp2_pilot", REPO_ROOT / "scripts" / "wp2_pilot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPORTS", tmp_path)
    (tmp_path / "calibration.json").write_text(
        json.dumps({"population": 500, "tournament": 3, "generations": 60,
                    "requested_evaluations": 30_500})
    )  # fmt: skip
    return module


def _budget(tmp_path, multiplier, base=None, unit="requested"):
    base = load_settings()["fitness"]["lambda_turnover"] if base is None else base
    (tmp_path / "budget_check.json").write_text(
        json.dumps({"budget_unit": {"unit": unit}, "lambda_turnover_multiplier": multiplier,
                    "base_lambda_turnover": base})
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
