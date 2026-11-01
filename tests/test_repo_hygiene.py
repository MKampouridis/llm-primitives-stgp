"""The repository must never contain data files, large files or secrets."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_hygiene", ROOT / "scripts" / "check_hygiene.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_tracked() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [line for line in out.splitlines() if line]


def test_tracked_files_are_clean():
    checker = _load_checker()
    assert checker.check(_git_tracked(), ROOT) == []


@pytest.mark.parametrize(
    "name",
    ["prices.parquet", "raw/spx.csv", ".env", ".env.local", "id_ed25519", "config/paths.toml"],
)
def test_checker_rejects_forbidden_files(tmp_path, name):
    checker = _load_checker()
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x")
    assert checker.check([name], tmp_path), name


def test_checker_rejects_secret_strings(tmp_path):
    checker = _load_checker()
    fake = "sk-" + "ant-" + "a" * 30
    (tmp_path / "settings.py").write_text(f'KEY = "{fake}"\n')
    assert checker.check(["settings.py"], tmp_path)


def test_checker_allows_env_example(tmp_path):
    checker = _load_checker()
    (tmp_path / ".env.example").write_text("ANTHROPIC_API_KEY=\n")
    assert checker.check([".env.example"], tmp_path) == []


def test_only_the_trial_register_may_be_a_tracked_csv(tmp_path):
    checker = _load_checker()
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "configuration_register.csv").write_text("config,digest\n")
    (tmp_path / "reports" / "other.csv").write_text("x\n")
    (tmp_path / "configuration_register.csv").write_text("x\n")
    assert checker.check(["reports/configuration_register.csv"], tmp_path) == []
    assert checker.check(["reports/other.csv"], tmp_path)
    assert checker.check(["configuration_register.csv"], tmp_path)  # only at its own path
