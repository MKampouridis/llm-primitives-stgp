from pathlib import Path, PurePosixPath

import pytest

from lpstgp.backup import SUPERSEDED, mirror, wanted


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def work(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "work"
    _write(root / "docs/plan.md", "plan")
    _write(root / "results/tierA/run.json", "{}")
    _write(root / "data/tierA/manifest.csv", "m")
    _write(root / "data/tierA/raw/yahoo/SPX/20261030.csv", "raw")
    _write(root / "data/tierA/processed/SPX.parquet", "processed")
    _write(root / "data/tierC/dcgp/prices.txt", "essex")
    _write(root / "docs/.DS_Store", "x")
    return {tree: root / tree for tree in ("docs", "results", "data")}


def _tree(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_selection_keeps_raw_manifests_and_tier_c_only():
    assert wanted("data", PurePosixPath("tierA/raw/yahoo/SPX/1.csv"))
    assert wanted("data", PurePosixPath("tierA/manifest.csv"))
    assert wanted("data", PurePosixPath("tierC/any/file.txt"))
    assert not wanted("data", PurePosixPath("tierA/processed/SPX.parquet"))
    assert not wanted("data", PurePosixPath("stray.csv"))
    assert not wanted("docs", PurePosixPath("a/.DS_Store"))
    assert wanted("results", PurePosixPath("tierA/x/run.json"))


def test_mirror_copies_then_is_idempotent(work, tmp_path):
    target = tmp_path / "box"
    first = mirror(work, target, "t1")
    assert _tree(target) == {
        "docs/plan.md",
        "results/tierA/run.json",
        "data/tierA/manifest.csv",
        "data/tierA/raw/yahoo/SPX/20261030.csv",
        "data/tierC/dcgp/prices.txt",
    }
    assert len(first.copied) == 5
    assert not first.superseded
    second = mirror(work, target, "t2")
    assert not second.copied
    assert not second.superseded
    assert second.unchanged == 5


def test_changed_and_removed_files_are_superseded_not_lost(work, tmp_path):
    target = tmp_path / "box"
    mirror(work, target, "t1")
    _write(work["docs"] / "plan.md", "plan v2")
    (work["results"] / "tierA/run.json").unlink()
    report = mirror(work, target, "t2")
    assert report.copied == ["docs/plan.md"]
    assert report.superseded == ["docs/plan.md", "results/tierA/run.json"]
    assert (target / "docs/plan.md").read_text() == "plan v2"
    assert (target / SUPERSEDED / "t2/docs/plan.md").read_text() == "plan"
    assert (target / SUPERSEDED / "t2/results/tierA/run.json").exists()
    assert not (target / "results/tierA").exists()  # emptied directories are removed


def test_dry_run_writes_nothing(work, tmp_path):
    target = tmp_path / "box"
    target.mkdir()
    report = mirror(work, target, "t1", dry_run=True)
    assert len(report.copied) == 5
    assert not any(target.iterdir())


def test_overlapping_target_is_refused(work):
    with pytest.raises(ValueError, match="overlaps"):
        mirror(work, work["docs"] / "mirror", "t1")
