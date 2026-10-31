"""Frozen whole strategies: ``generated/<domain>/s<NN>__v1.py`` plus ``strategies.lock.toml``.

Files are the LLM's text, verbatim (excluded from formatting). The lock stores each file's
sha256 and provenance; ``load_frozen`` refuses a file whose hash differs from the lock.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

from lpstgp.operators.contract import Provenance
from lpstgp.strategies.adapters import Frozen
from lpstgp.strategies.loader import load_file

STRATEGIES_DIR = Path(__file__).resolve().parent
GENERATED_DIR = STRATEGIES_DIR / "generated"
LOCK_FILE = STRATEGIES_DIR / "strategies.lock.toml"
_FILE = re.compile(r"^(s\d{2})__v1\.py$")


class LockMismatchError(RuntimeError):
    """A frozen strategy file differs from its locked hash."""


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strategy_files(root: Path = GENERATED_DIR) -> dict[str, Path]:
    found = {}
    for path in sorted(root.glob("*/s*__v1.py")):
        match = _FILE.match(path.name)
        if match:
            found[match.group(1)] = path
    return found


def read_lock(path: Path = LOCK_FILE) -> dict[str, dict]:
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def lock_digest(path: Path = LOCK_FILE) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def load_frozen(root: Path = GENERATED_DIR, lock_path: Path = LOCK_FILE) -> tuple[Frozen, ...]:
    lock = read_lock(lock_path)
    frozen = []
    for sid, path in strategy_files(root).items():
        entry = lock.get(sid)
        sha = file_hash(path)
        if entry is None or entry["sha256"] != sha:
            raise LockMismatchError(f"{sid}: {path.name} is not locked or differs from its lock")
        strategy = load_file(path, module_name=f"lpstgp_strategy_{sid}")
        frozen.append(Frozen(sid, strategy, sha, Provenance(**entry["provenance"])))
    return tuple(frozen)


def write_lock(entries: dict[str, dict], path: Path = LOCK_FILE) -> None:
    """Write the lock (used once, when generation freezes the set)."""
    lines = ["# Frozen whole strategies (WP2). Do not edit: regenerate with the freeze step.\n"]
    for sid in sorted(entries):
        entry = entries[sid]
        lines.append(f'\n[{sid}]\nsha256 = "{entry["sha256"]}"\nfile = "{entry["file"]}"\n')
        lines.append(f"[{sid}.provenance]\n")
        for key, value in entry["provenance"].items():
            if value is not None:
                lines.append(f"{key} = {value!r}\n".replace("'", '"'))
    path.write_text("".join(lines), encoding="utf-8")
