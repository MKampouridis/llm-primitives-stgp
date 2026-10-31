"""WP2 data cap (2008-07-01), pilot and development periods, and the pilot-only test stage."""

import ast
import json
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from lpstgp.config import REPO_ROOT, load_settings
from lpstgp.data.store import HorizonCapError
from lpstgp.freeze import FreezeError, FreezeManifest, write_manifest
from lpstgp.sandbox import Sandbox, SealedPeriodError
from lpstgp.splits import Stage, all_periods, development_period, pilot_periods

from .test_sandbox import LMAX, _frame, _store

SETTINGS = load_settings()
CAP = SETTINGS["leakage"]["max_horizon"]
PERIODS = all_periods(SETTINGS)
PL1, PL2 = pilot_periods(SETTINGS)
DEV = development_period(SETTINGS)


def _capped(tmp_path, name, frame):
    store = _store(tmp_path, name, frame)
    store.max_horizon = CAP
    return store


def test_pilot_and_development_periods():
    assert date(2008, 7, 1) == CAP
    assert (PL1.fit_start, PL1.val_start, PL1.test_start, PL1.test_end) == (
        date(2003, 7, 1),
        date(2005, 7, 1),
        date(2006, 7, 1),
        date(2007, 7, 1),
    )
    assert PL2.test_end == CAP == PERIODS["P01"].test_start
    assert (DEV.fit_start, DEV.val_start, DEV.test_start) == (
        date(1995, 7, 1),
        date(2003, 7, 1),
        date(2005, 7, 1),
    )
    # the development window ends before every pilot validation year
    assert DEV.horizon(Stage.VALIDATE) <= PL1.val_start
    assert len(PERIODS) == 18 + 2 + 1


def test_capped_store_refuses_reads_past_the_cap(tmp_path):
    store = _capped(tmp_path, "clean", _frame())
    store.read("TST", date(2007, 1, 1), CAP)  # up to the cap is fine
    with pytest.raises(HorizonCapError):
        store.read("TST", date(2007, 1, 1), date(2008, 7, 2))


@pytest.mark.parametrize(
    ("period_id", "stage", "allowed"),
    [
        ("P01", Stage.FIT, True),
        ("P01", Stage.VALIDATE, True),  # horizon == cap
        ("P02", Stage.FIT, True),
        ("P02", Stage.VALIDATE, False),
        ("P18", Stage.FIT, False),
        ("PL1", Stage.VALIDATE, True),
        ("PL2", Stage.VALIDATE, True),
        ("DEV", Stage.FIT, True),
    ],
)
def test_sandbox_respects_the_cap(tmp_path, period_id, stage, allowed):
    store = _capped(tmp_path, "clean", _frame())
    if allowed:
        Sandbox.open(store, PERIODS[period_id], stage, ["TST"], LMAX)
    else:
        with pytest.raises(SealedPeriodError, match="data cap"):
            Sandbox.open(store, PERIODS[period_id], stage, ["TST"], LMAX)


@pytest.mark.parametrize(
    ("period_id", "stage", "poison_from"),
    [
        ("PL2", Stage.VALIDATE, "2007-07-01"),
        ("P01", Stage.VALIDATE, "2008-07-01"),
        ("DEV", Stage.FIT, "2003-07-01"),
        ("DEV", Stage.VALIDATE, "2005-07-01"),
    ],
)
def test_poisoned_future_is_invisible_in_wp2_periods(tmp_path, period_id, stage, poison_from):
    period = PERIODS[period_id]
    clean = Sandbox.open(_capped(tmp_path, "c", _frame()), period, stage, ["TST"], LMAX)["TST"]
    dirty = Sandbox.open(_capped(tmp_path, "d", _frame(poison_from)), period, stage, ["TST"], LMAX)
    for name in ("dates", "close", "log_return", "log_price"):
        np.testing.assert_array_equal(getattr(clean, name), getattr(dirty["TST"], name))


def _committed_manifest(tmp_path: Path) -> FreezeManifest:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "t@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "t"], check=True)
    path = repo / "freeze.json"
    write_manifest(path, {"PL1/TST/run1": "abc"}, {"settings": "x"})
    subprocess.run([*git, "add", "freeze.json"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "freeze"], check=True)
    return FreezeManifest.load_committed(path, repo=repo)


def test_pilot_test_stage_needs_pilot_period_cap_and_committed_manifest(tmp_path):
    store = _capped(tmp_path, "clean", _frame())
    manifest = _committed_manifest(tmp_path)
    pilots = pilot_periods(SETTINGS)
    box = Sandbox.open_pilot_test(
        store, PL1, ["TST"], LMAX, pilot_periods=pilots, manifest=manifest
    )
    assert box.stage is Stage.TEST
    assert box["TST"].dates[-1] < np.datetime64(PL1.test_end)
    with pytest.raises(SealedPeriodError, match="pilot"):  # primary period
        Sandbox.open_pilot_test(
            store, PERIODS["P01"], ["TST"], LMAX, pilot_periods=pilots, manifest=manifest
        )
    forged = replace(PL1, test_end=date(2009, 7, 1))  # same id, later dates
    with pytest.raises(SealedPeriodError, match="pilot"):
        Sandbox.open_pilot_test(
            store, forged, ["TST"], LMAX, pilot_periods=pilots, manifest=manifest
        )
    with pytest.raises(SealedPeriodError, match="manifest"):
        Sandbox.open_pilot_test(store, PL1, ["TST"], LMAX, pilot_periods=pilots, manifest=None)
    uncapped = _store(tmp_path, "uncapped", _frame())
    with pytest.raises(SealedPeriodError, match="cap"):
        Sandbox.open_pilot_test(
            uncapped, PL1, ["TST"], LMAX, pilot_periods=pilots, manifest=manifest
        )
    with pytest.raises(SealedPeriodError):  # the ordinary entry point stays sealed
        Sandbox.open(store, PL1, Stage.TEST, ["TST"], LMAX)


def test_freeze_manifest_must_be_committed_and_intact(tmp_path):
    manifest = _committed_manifest(tmp_path)
    manifest.require("PL1/TST/run1", "abc")
    with pytest.raises(FreezeError):
        manifest.require("PL1/TST/run1", "abd")
    path = manifest.path
    data = json.loads(path.read_text())
    data["rules"]["PL1/TST/run2"] = "zzz"  # edited after the commit
    path.write_text(json.dumps(data))
    with pytest.raises(FreezeError, match="differs from HEAD"):
        FreezeManifest.load_committed(path, repo=path.parent)
    loose = path.parent / "untracked.json"
    write_manifest(loose, {}, {})
    with pytest.raises(FreezeError, match="not tracked"):
        FreezeManifest.load_committed(loose, repo=path.parent)


def test_modelling_entry_points_use_the_capped_store():
    """Only the factory in data/store.py may construct a DataStore in src/ and scripts/."""
    offenders = []
    for path in [
        *REPO_ROOT.joinpath("src").rglob("*.py"),
        *REPO_ROOT.joinpath("scripts").glob("*.py"),
    ]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "DataStore"
                and path.name != "store.py"
            ):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, offenders
