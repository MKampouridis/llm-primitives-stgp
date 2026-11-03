"""Library states of the maintained arms: content-addressed operator sets with a manifest (§5).

A state is a directory ``<results>/wp3/states/<id>/`` holding ``manifest.json`` and the operator
files (``files/<name>__v<k>.py``, verbatim LLM output). The id is the sha256 (first 16 hex) of the
canonical manifest, so equal libraries have equal ids. The GP resolves a state through the library
name ``state:<id>``: the WP1 data terminals and core glue plus the state's operators, each file
checked against its hash before it is loaded. States are never modified; a patch makes a new one.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Any

from lpstgp.authoring import loader
from lpstgp.authoring import registry as authored
from lpstgp.operators.contract import OperatorSpec, Provenance, TerminalSpec

PREFIX = "state:"


@dataclass(frozen=True)
class Entry:
    name: str
    version: int
    domain: str
    sha256: str
    provenance: Mapping[str, str]
    entered: str  # "arm3" or "<arm>/<period>/c<k>"
    parent: str | None = None  # key (name@version) this one refines

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def file(self) -> str:
        return f"files/{self.name}__v{self.version}.py"


@dataclass(frozen=True)
class LibraryState:
    entries: tuple[Entry, ...]
    meta: Mapping[str, Any] = field(default_factory=dict)  # not part of the id; never used in
    # decisions (D-074: an equal state reached by another lineage keeps the first one's meta)

    def manifest(self) -> dict[str, Any]:
        return {"operators": [asdict(e) for e in sorted(self.entries, key=lambda e: e.key)]}

    @property
    def id(self) -> str:
        text = json.dumps(self.manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    @property
    def library_name(self) -> str:
        return PREFIX + self.id

    def by_name(self) -> dict[str, Entry]:
        return {e.name: e for e in self.entries}

    def with_changes(
        self, remove: Sequence[str] = (), add: Sequence[Entry] = (), meta: Mapping | None = None
    ) -> LibraryState:
        kept = tuple(e for e in self.entries if e.name not in set(remove))
        names = [e.name for e in (*kept, *add)]
        if len(names) != len(set(names)):
            raise ValueError("a library state may hold only one version of each operator")
        return replace(self, entries=(*kept, *add), meta=dict(meta or {}))


def states_root(results_dir: Path) -> Path:
    return Path(results_dir) / "wp3" / "states"


def save(state: LibraryState, sources: Mapping[str, Path], results_dir: Path) -> Path:
    """Write a state (idempotent). ``sources`` maps each new entry's key to its file; entries
    already stored in another state are found by hash."""
    root = states_root(results_dir) / state.id
    if (root / "manifest.json").exists():
        return root
    tmp = root.with_name(root.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "files").mkdir(parents=True)
    for e in state.entries:
        source = sources.get(e.key) or _stored(e, results_dir)
        if authored.file_hash(source) != e.sha256:
            raise ValueError(f"{e.key}: file differs from its hash")
        shutil.copyfile(source, tmp / e.file)
    manifest = {**state.manifest(), "meta": dict(state.meta)}
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    tmp.rename(root)
    return root


def _stored(entry: Entry, results_dir: Path) -> Path:
    if entry.entered == "arm3":
        lock = authored.read_lock("arm3")[entry.name]
        return authored.GENERATED_DIR / "arm3" / lock["file"]
    for path in states_root(results_dir).glob(f"*/{entry.file}"):
        if authored.file_hash(path) == entry.sha256:
            return path
    raise FileNotFoundError(f"{entry.key}: no stored file with hash {entry.sha256[:12]}")


def read(state_id: str, results_dir: Path) -> LibraryState:
    data = json.loads((states_root(results_dir) / state_id / "manifest.json").read_text())
    state = LibraryState(tuple(Entry(**e) for e in data["operators"]), data.get("meta", {}))
    if state.id != state_id:
        raise ValueError(f"state {state_id}: manifest does not match its id")
    return state


def arm3_state() -> LibraryState:
    """The starting state of every maintained arm: arm 3's frozen library (D-063)."""
    entries = []
    for name, lock in authored.read_lock("arm3").items():
        entries.append(
            Entry(name, 1, lock["domain"], lock["sha256"], dict(lock["provenance"]), "arm3")
        )
    return LibraryState(tuple(entries))


@cache
def load_specs(state_id: str, results_dir: str) -> tuple[OperatorSpec, ...]:
    state = read(state_id, Path(results_dir))
    root = states_root(Path(results_dir)) / state_id
    specs = []
    for e in sorted(state.entries, key=lambda e: e.key):
        path = root / e.file
        if authored.file_hash(path) != e.sha256:
            raise authored.LockMismatchError(f"state {state_id}: {e.file} differs from its hash")
        spec = loader.to_spec(
            loader.load_operator(path), e.domain, Provenance(**e.provenance), version=e.version
        )
        if spec.name != e.name:
            raise authored.LockMismatchError(f"{e.file} defines {spec.name}, not {e.name}")
        specs.append(spec)
    return tuple(specs)


def library(name: str) -> list[OperatorSpec | TerminalSpec]:
    """Specs of the library ``state:<id>`` (data terminals, core glue and the state's operators)."""
    from lpstgp.config import load_paths
    from lpstgp.operators.registry import discover

    state_id = name.removeprefix(PREFIX)
    return [
        *discover().domain("data", "core"),
        *load_specs(state_id, str(load_paths().results_dir)),
    ]
