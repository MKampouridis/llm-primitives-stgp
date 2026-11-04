"""The data-cap mechanism (WP2 cap of 2008-07-01, given explicitly), pilot and development
periods, the pilot-only test stage, and the WP4 stage sealing (D-080)."""

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
CAP = date(2008, 7, 1)  # the WP2 cap (D-034): the mechanism is tested with it; WP4 uses D-080
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
    assert len(PERIODS) == 18 + 1 + 2 + 1 + 3  # P01..P18, PC, the pilots, DEV, G1-G3 (D-092)


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
    with pytest.raises(SealedPeriodError, match="pilot"):  # a WP4 period passed as a pilot
        Sandbox.open_pilot_test(
            store, PERIODS["P01"], ["TST"], LMAX, pilot_periods=[PERIODS["P01"]],
            manifest=manifest,
        )  # fmt: skip


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


def test_pilot_test_stage_refuses_hand_built_or_empty_manifests(tmp_path):
    store = _capped(tmp_path, "clean", _frame())
    pilots = pilot_periods(SETTINGS)
    forged = FreezeManifest(Path("nowhere.json"), "not-a-commit", {"PL1/TST/run1": "abc"}, {})
    with pytest.raises(SealedPeriodError, match="manifest"):
        Sandbox.open_pilot_test(store, PL1, ["TST"], LMAX, pilot_periods=pilots, manifest=forged)
    loaded = _committed_manifest(tmp_path)
    empty = replace(loaded, rules={})
    with pytest.raises(SealedPeriodError, match="manifest"):
        Sandbox.open_pilot_test(store, PL1, ["TST"], LMAX, pilot_periods=pilots, manifest=empty)


def test_freeze_context_must_be_unchanged_at_the_test_read(tmp_path):
    manifest = _committed_manifest(tmp_path)
    manifest.check_context({"settings": "x"})
    with pytest.raises(FreezeError, match="settings"):
        manifest.check_context({"settings": "y"})
    with pytest.raises(FreezeError, match="operator_lock"):
        manifest.check_context({"settings": "x", "operator_lock": "new"})


@pytest.mark.parametrize("period_id", ["P01", "P02"])
def test_an_allowed_period_list_refuses_the_others(tmp_path, period_id):
    """The mechanism WP2 used to keep P01..P18 out while their windows overlapped the pilot test
    years (D-047)."""
    store = _capped(tmp_path, "clean", _frame())
    store.allowed_periods = frozenset({"DEV", "PL1", "PL2"})
    with pytest.raises(SealedPeriodError, match="allowed_periods"):
        Sandbox.open(store, PERIODS[period_id], Stage.FIT, ["TST"], LMAX)
    assert len(Sandbox.open(store, PL1, Stage.VALIDATE, ["TST"], LMAX)["TST"].dates)


def test_wp4_settings_open_fit_and_validate_of_every_period_and_cap_at_pc_test():
    """D-080: stage sealing over P01..P18 and PC; the cap is the PC test start."""
    from lpstgp.data.store import modelling_store

    pc = PERIODS["PC"]
    assert (pc.fit_start, pc.val_start, pc.test_start) == (
        date(2023, 7, 1), date(2025, 7, 1), date(2026, 7, 1),
    )  # fmt: skip
    assert SETTINGS["leakage"]["max_horizon"] == pc.test_start == PERIODS["P18"].test_end
    store = modelling_store(REPO_ROOT / "nowhere", SETTINGS)
    primary = {f"P{k:02d}" for k in range(1, 19)}
    assert store.allowed_periods == {"DEV", "G1", "G2", "G3", "PL1", "PL2", "PC", *primary}


@pytest.mark.parametrize("period_id", ["P01", "P09", "P18", "PC", "PL1", "DEV"])
def test_every_test_stage_stays_sealed_under_wp4_settings(tmp_path, period_id):
    store = _store(tmp_path, "clean", _frame())
    store.max_horizon = SETTINGS["leakage"]["max_horizon"]
    period = PERIODS[period_id]
    with pytest.raises(SealedPeriodError, match="sealed"):
        Sandbox.open(store, period, Stage.TEST, ["TST"], LMAX)
    if period_id not in ("PL1", "DEV"):
        with pytest.raises(SealedPeriodError, match="pilot"):  # no pilot read for them either
            Sandbox.open_pilot_test(
                store, period, ["TST"], LMAX, pilot_periods=(PL1, PL2), manifest=None
            )


def test_pc_validation_reads_stop_before_the_cap(tmp_path):
    store = _store(tmp_path, "clean", _frame())
    store.max_horizon = SETTINGS["leakage"]["max_horizon"]
    with pytest.raises(HorizonCapError):
        store.read("TST", date(2026, 1, 1), date(2026, 7, 2))


def test_the_test_read_can_be_claimed_only_once(tmp_path):
    from lpstgp.freeze import claim_test_read

    manifest = _committed_manifest(tmp_path)
    claim = tmp_path / "claim.json"
    claim_test_read(claim, manifest)
    assert json.loads(claim.read_text())["manifest_commit"] == manifest.commit
    with pytest.raises(FreezeError, match="already been claimed"):
        claim_test_read(claim, manifest)  # e.g. a rerun after a crash, or a second process


def test_a_period_with_shifted_dates_is_refused_by_the_modelling_store(tmp_path):
    """D-087: the settings' named periods only; P01 with its test start moved to its test end
    would otherwise open P01's test year as 'VALIDATE'."""
    from lpstgp.data.store import modelling_store
    from lpstgp.splits import all_periods

    _store(tmp_path, "s", _frame())
    store = modelling_store(tmp_path / "s", SETTINGS)
    p01 = all_periods(SETTINGS)["P01"]
    Sandbox.open(store, p01, Stage.VALIDATE, ["TST"], LMAX)
    shifted = replace(p01, test_start=p01.test_end)
    with pytest.raises(SealedPeriodError, match="dates differ"):
        Sandbox.open(store, shifted, Stage.VALIDATE, ["TST"], LMAX)


def test_data_digests_ignore_later_bars_and_provenance_but_not_earlier_rows(tmp_path):
    """D-087: PC's test year, added later, and a rebuild leave every digest unchanged."""
    import pandas as pd
    from tests.leakage.test_sandbox import META

    from lpstgp.campaign.plan import digest_horizon, rows_digest
    from lpstgp.data import schema

    horizon = digest_horizon()
    dates = pd.bdate_range("2020-01-01", "2027-06-30")
    rng = np.random.default_rng(9)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(dates))))
    frame = pd.DataFrame({"date": dates, "close": close})
    path = tmp_path / "X.parquet"

    def write(f, **meta):
        bars, _ = schema.normalise(f)
        schema.write_parquet(bars, {**META, **meta}, path)
        return rows_digest(path)

    early = frame[frame["date"] < pd.Timestamp(horizon)]
    base = write(early)
    assert write(frame) == base  # bars from the horizon on are not digested
    assert write(frame, built_at_utc="later", raw_files=[{"file": "x"}]) == base
    assert write(frame, cost_bps=9.0) != base  # metadata that changes results
    revised = frame.copy()
    revised.loc[10, "close"] *= 1.01
    assert write(revised) != base  # an earlier row revised
