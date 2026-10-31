"""One-way backup mirror of the working copy: docs, reports, results, raw data and manifests.

The mirror (``backup_dir`` in ``config/paths.toml``, e.g. a Box folder) is written only by this
module and never edited by hand. Nothing is lost when a file changes or disappears from the
working copy: the mirror's previous copy moves to ``_superseded/<UTC timestamp>/`` first.
Processed data (rebuildable from raw files), caches and the environment are not mirrored.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SUPERSEDED = "_superseded"
IGNORED_NAMES = frozenset({".DS_Store", "Thumbs.db"})
IGNORED_DIRS = frozenset({"__pycache__", ".ipynb_checkpoints"})

README = """# BACKUP MIRROR (do not edit)

This folder is a one-way backup of the llm-primitives-stgp project, written by
`scripts/backup.py`. Do not edit or add files here: the next backup may move them away.

- Working copy: `~/code/llm-primitives-stgp` (code, docs, reports; data, results and caches are
  git-ignored there). Code and docs are also on GitHub: MKampouridis/llm-primitives-stgp (private).
- Mirrored: `docs/`, `reports/`, `results/`, and from `data/` only the raw downloads, manifests
  and Tier C datasets (processed Parquet files are rebuilt from the raw files).
- `{superseded}/<UTC timestamp>/` keeps earlier copies of files that later changed or were removed.

Last backup: {stamp} (code {revision}).
"""


@dataclass
class Report:
    copied: list[str] = field(default_factory=list)
    superseded: list[str] = field(default_factory=list)
    unchanged: int = 0
    bytes_copied: int = 0


def wanted(tree: str, rel: PurePosixPath) -> bool:
    """Whether ``tree/rel`` belongs in the mirror."""
    if rel.name in IGNORED_NAMES or IGNORED_DIRS.intersection(rel.parts):
        return False
    if tree != "data":
        return True
    parts = rel.parts
    if len(parts) < 2 or not parts[0].startswith("tier"):
        return False
    if parts[0] == "tierC":  # copied datasets cannot be downloaded again
        return True
    return parts[1] == "raw" or (len(parts) == 2 and parts[1].startswith("manifest"))


def _files(root: Path) -> Iterator[PurePosixPath]:
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                yield PurePosixPath(path.relative_to(root).as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _same(a: Path, b: Path) -> bool:
    return a.stat().st_size == b.stat().st_size and _sha256(a) == _sha256(b)


def mirror(
    sources: Mapping[str, Path], target: Path, stamp: str, *, dry_run: bool = False
) -> Report:
    """Mirror each ``sources[tree]`` into ``target/tree``; ``stamp`` names the superseded folder."""
    target = target.resolve()
    for tree, root in sources.items():
        root = root.resolve()
        if root == target or target.is_relative_to(root) or root.is_relative_to(target):
            raise ValueError(f"backup target {target} overlaps the source {tree} at {root}")
    if not target.parent.is_dir():
        raise FileNotFoundError(f"parent of the backup target is missing: {target.parent}")
    report = Report()
    archive = target / SUPERSEDED / stamp

    def supersede(rel: str) -> None:
        report.superseded.append(rel)
        if not dry_run:
            destination = archive / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(target / rel, destination)

    for tree, root in sources.items():
        source_files = {rel for rel in _files(root) if wanted(tree, rel)}
        for rel in source_files:
            src, dst = root / rel, target / tree / rel
            if dst.is_file() and _same(src, dst):
                report.unchanged += 1
                continue
            if dst.exists():
                supersede(f"{tree}/{rel}")
            report.copied.append(f"{tree}/{rel}")
            report.bytes_copied += src.stat().st_size
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        for rel in _files(target / tree):
            if rel not in source_files:
                supersede(f"{tree}/{rel}")
    if not dry_run:
        for tree in sources:  # drop directories emptied by superseding
            for path in sorted((target / tree).rglob("*"), reverse=True):
                if path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
    report.copied.sort()
    report.superseded.sort()
    return report


def write_readme(target: Path, stamp: str, revision: str) -> None:
    text = README.format(superseded=SUPERSEDED, stamp=stamp, revision=revision)
    (target / "README.md").write_text(text, encoding="utf-8")
