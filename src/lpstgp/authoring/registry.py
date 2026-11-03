"""Frozen LLM-authored operator libraries: ``generated/<arm>/<domain>/<name>__v1.py`` plus a lock.

As the WP2 strategies (D-038): the accepted files are copied byte for byte from the session
archives and never edited; ``<arm>.lock.toml`` stores each file's sha256, domain and provenance,
and :func:`load_library` refuses a file that differs from its lock. The files live outside
``lpstgp.operators`` so that :func:`lpstgp.operators.registry.discover` (the WP1 registry and
arm 6) never sees them; a named library ``arm3`` is the data terminals, the core glue and these
operators (D-063, protocol_wp3 §3).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from lpstgp.authoring import loader
from lpstgp.operators.contract import OperatorSpec, Provenance, TerminalSpec

AUTHORING_DIR = Path(__file__).resolve().parent
GENERATED_DIR = AUTHORING_DIR / "generated"
ARMS = ("arm3",)


class LockMismatchError(RuntimeError):
    """A frozen operator file is missing from its lock or differs from it."""


def lock_path(arm: str) -> Path:
    return AUTHORING_DIR / f"{arm}.lock.toml"


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_lock(arm: str) -> dict[str, dict]:
    path = lock_path(arm)
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def lock_digest(arm: str) -> str:
    path = lock_path(arm)
    return file_hash(path) if path.exists() else ""


@cache
def load_library(arm: str = "arm3") -> tuple[OperatorSpec, ...]:
    """The frozen operators of an arm, in lock order, after checking every file's hash."""
    if arm not in ARMS:
        raise KeyError(f"unknown authored library {arm!r}; known: {ARMS}")
    lock = read_lock(arm)
    if not lock:
        raise LockMismatchError(f"{arm}: no operators are locked yet")
    root = GENERATED_DIR / arm
    on_disk = {p.relative_to(root).as_posix() for p in root.glob("*/*__v1.py")}
    locked = {entry["file"] for entry in lock.values()}
    if on_disk != locked:
        raise LockMismatchError(f"{arm}: files on disk differ from the lock: {on_disk ^ locked}")
    specs = []
    for name, entry in lock.items():
        path = root / entry["file"]
        if file_hash(path) != entry["sha256"]:
            raise LockMismatchError(f"{arm}/{entry['file']} differs from its locked hash")
        spec = loader.load_spec(path, entry["domain"], Provenance(**entry["provenance"]))
        if spec.name != name:
            raise LockMismatchError(f"{arm}/{entry['file']} defines {spec.name}, locked as {name}")
        specs.append(spec)
    return tuple(specs)


def library(arm: str = "arm3") -> list[OperatorSpec | TerminalSpec]:
    """The named GP library of an arm: data terminals, core glue and the arm's operators."""
    from lpstgp.operators.registry import discover

    return [*discover().domain("data", "core"), *load_library(arm)]


# --- freezing (run once per arm, by scripts/freeze_authored.py) -------------------------------


def accepted_sessions(archive_root: Path) -> list[dict[str, Any]]:
    """Accepted session summaries in domain order (a re-run replaces its failed first attempt)."""
    out = []
    for path in sorted(archive_root.glob("a??_*/summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        summary["archive"] = str(path.parent)
        if summary.get("accepted"):
            out.append(summary)
    return out


def freeze(arm: str, accepted: Sequence[Mapping[str, Any]]) -> dict[str, dict]:
    """Copy each accepted file verbatim and write the lock; refuses any hash mismatch."""
    root = GENERATED_DIR / arm
    if read_lock(arm) or root.exists():
        raise RuntimeError(f"{arm} is already frozen; a change needs new version files")
    entries: dict[str, dict] = {}
    for s in accepted:
        for row in s["operators"]:
            source = Path(s["archive"]) / "final" / row["file"]
            if file_hash(source) != row["sha256"]:
                raise RuntimeError(f"{s['slot']}/{row['file']}: archived file differs")
            name = row["operator"]["name"]
            if name in entries:
                raise RuntimeError(f"{name} is defined twice")
            target = root / s["domain"] / f"{name}__v1.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            entries[name] = {
                "sha256": row["sha256"],
                "file": f"{s['domain']}/{target.name}",
                "domain": s["domain"],
                "provenance": {
                    "implemented_by": (
                        f"{s['model']} via Claude Code {s['claude_version']} (headless session "
                        f"{s['session_id']}, effort {s['effort']})"
                    ),
                    "specified_by": f"WP3 arm-3 authoring protocol, brief {s['brief_sha12']}",
                    "date": s["finished_utc"][:10],
                },
            }
    _write_lock(arm, entries)
    return entries


def _write_lock(arm: str, entries: Mapping[str, Mapping[str, Any]]) -> None:
    lines = [f"# Frozen LLM-authored operators ({arm}, WP3). Do not edit: written by the freeze.\n"]
    for name, entry in entries.items():
        lines.append(
            f'\n[{name}]\nsha256 = "{entry["sha256"]}"\nfile = "{entry["file"]}"\n'
            f'domain = "{entry["domain"]}"\n[{name}.provenance]\n'
        )
        for key, value in entry["provenance"].items():
            lines.append(f"{key} = {json.dumps(value)}\n")
    lock_path(arm).write_text("".join(lines), encoding="utf-8")
