"""End-to-end rehearsal of WP4's reported runs, freeze and single test read (protocol_wp4 §6),
on synthetic instruments, in a throwaway git repository (as D-052 did for WP2).

Every arm is planned for P01 and P02 at a tiny scale. The maintained arms take a fake M3
campaign whose last cycles hold arm 3's state. Then the runs, freeze, commit, the go-ahead
check, the validation rehearsal, the one read and its claim. Nothing in the real repository is
touched.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from lpstgp.campaign.plan import Config
from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.data import schema
from lpstgp.freeze import FreezeError
from lpstgp.gates.synthetic import garch_returns

INSTRUMENTS = ("AAA", "BBB")
PERIODS = ("P01", "P02")
TINY = {"population": 8, "generations": 1, "tournament": 3}


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _synthetic_tier(root):
    dates = pd.bdate_range("2002-01-01", "2010-12-31")
    for k, name in enumerate(INSTRUMENTS):
        r = garch_returns(len(dates), 500 + k)
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
def driver(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    for part in ("src", "scripts", "config"):
        shutil.copytree(
            REPO_ROOT / part, repo / part,
            ignore=shutil.ignore_patterns("__pycache__", "paths.toml", "*.pyc"),
        )  # fmt: skip
    reports = repo / "reports" / "wp4"
    reports.mkdir(parents=True)
    (reports / "eligibility.json").write_text(
        json.dumps({"eligible": {p: list(INSTRUMENTS) for p in PERIODS}})
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "decisions.md").write_text(
        "### D-999 WP4 test read: go-ahead (PI, rehearsal)\n"
    )
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
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    wp4 = importlib.import_module("wp4")
    wp2 = importlib.import_module("wp2_pilot")
    monkeypatch.setattr(wp4, "REPO_ROOT", repo)
    monkeypatch.setattr(wp4, "REPORTS", reports)
    monkeypatch.setattr(wp4, "RUNS", 2)
    monkeypatch.setattr(wp2, "REPO_ROOT", repo)
    monkeypatch.setattr(wp2, "register", lambda: tmp_path / "register.csv")
    monkeypatch.setattr(
        wp4, "gp_arm", lambda name, library, settings: Config(name, library, gp=TINY)
    )
    # a fake M3 campaign: every maintained arm ends each period on arm 3's state
    from lpstgp.maintenance import state

    paths = load_paths()
    arm3 = state.arm3_state()
    state.save(arm3, {}, paths.results_dir)
    root = paths.results_dir / "wp3" / "maintenance" / "fake"
    for arm in ("4-grow", "4-full", "5"):
        for period in PERIODS:
            d = root / arm / period / "c3"
            d.mkdir(parents=True)
            (d / "cycle.json").write_text(
                json.dumps({"state_out": {"state_id": arm3.id, "seed_rules": []}})
            )
            (root / arm / period / "lineage.json").write_text("{}")
    yield wp4, repo, paths
    sys.modules.pop("wp4", None)


@pytest.mark.slow
def test_wp4_plans_freeze_and_reads_the_test_years_once(driver):
    from lpstgp.campaign.execute import execute_plan

    wp4, repo, paths = driver
    settings = load_settings()
    wp4.step_plan(paths, settings, PERIODS, "fake")
    for period in PERIODS:
        plan = json.loads(wp4.plan_path(paths, period).read_text())
        assert plan["record_format"] == "json.gz"
        assert len(plan["configs"]) == 11
        execute_plan(wp4.plan_path(paths, period), paths, settings, workers=2)
    with pytest.raises(FreezeError, match="not tracked"):  # nothing frozen yet
        wp4.step_test(paths, settings, list(PERIODS), "fake", "D-999")
    wp4.step_freeze(paths, settings, list(PERIODS), "fake")
    manifest = json.loads((wp4.REPORTS / "freeze_manifest.json").read_text())
    per_period = len(INSTRUMENTS) * (1 + 10 * 2)  # arm 1 + 10 GP arms x 2 runs
    assert {p: r["rules"] for p, r in manifest["rules"].items()} == dict.fromkeys(
        PERIODS, per_period
    )
    assert manifest["context"]["test_periods"] == list(PERIODS)
    _git(repo, "add", "reports/wp4/freeze_manifest.json")
    _git(repo, "commit", "-q", "-m", "freeze")
    with pytest.raises(SystemExit, match="no decision"):  # the PI's go-ahead must be recorded
        wp4.step_test(paths, settings, list(PERIODS), "fake", "D-998")
    wp4.step_test(paths, settings, list(PERIODS), "fake", "D-999")
    result = json.loads((wp4.REPORTS / "primary.json").read_text())
    assert len(result["comparisons"]) == 8
    assert "BH" in result["sharpe"]
    for period, access in result["test_access"].items():
        assert {a["stage"] for a in access} == {"test"}, period
        assert {a["instrument"] for a in access} == set(INSTRUMENTS)
    for kind in ("validation", "test"):
        for period in PERIODS:
            assert (paths.results_dir / "wp4" / kind / f"{period}.npz").exists()
    (wp4.REPORTS / "primary.json").unlink()  # even with the result gone, the claim holds
    with pytest.raises(FreezeError, match="already been claimed"):
        wp4.step_test(paths, settings, list(PERIODS), "fake", "D-999")
