"""A maintainer session's patch, read from its folder, and gates 1-2 of protocol_wp3 §4.3.

The folder starts with one file per operator of the current library, ``<name>.py`` (the current
version's verbatim code). What the session leaves behind is the patch:

- a new non-empty ``.py`` file is a **grow** (a new operator, with a new name; the file sets
  ``DOMAIN = "<domain>"`` to one of the seven domains);
- an edited file that still defines the same operator is a **refine** (a new version);
- an emptied (or whitespace-only) file is a **prune** (D-070: sessions cannot delete files).

Gate 1: every new or refined file passes the admission gates in the sandboxed worker, including
cross-process determinism. Gate 2: the arm's bounds and the library cap hold, and every prune
meets the evidence rule. A patch with any problem is rejected whole; the library stays as it was.
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lpstgp.authoring import generation
from lpstgp.authoring.mcp_tools import API_FILE
from lpstgp.maintenance import evidence
from lpstgp.maintenance.state import Entry, LibraryState
from lpstgp.strategies import execute

LIBRARY_CAP = 64  # cross-domain operators (D-067; fixed at protocol 1.0, D-073)
BOUNDS = {  # per cycle (D-067; fixed at protocol 1.0, D-073)
    "4-grow": {"grow": 2, "refine": 0, "prune": 0},
    "4-full": {"grow": 2, "refine": 2, "prune": 2},
}
DOMAINS = tuple(generation.DOMAINS)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blank(path: Path) -> bool:
    return not path.read_text(encoding="utf-8").strip()


def declared_domain(path: Path) -> str | None:
    """The file's top-level ``DOMAIN = "..."`` string, if any (read without executing it)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and [getattr(t, "id", None) for t in node.targets] == ["DOMAIN"]
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def initial_files(state: LibraryState, stored: Mapping[str, Path], folder: Path) -> dict[str, str]:
    """Write the current library into the session folder; returns file name -> operator name."""
    files = {}
    for e in sorted(state.entries, key=lambda e: e.name):
        target = folder / f"{e.name}.py"
        target.write_bytes(stored[e.key].read_bytes())
        files[target.name] = e.name
    return files


@dataclass
class Patch:
    grows: list[dict[str, Any]] = field(default_factory=list)
    refines: list[dict[str, Any]] = field(default_factory=list)
    prunes: list[str] = field(default_factory=list)  # operator names
    problems: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.grows or self.refines or self.prunes)

    @property
    def admissible(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "grows": self.grows,
            "refines": self.refines,
            "prunes": self.prunes,
            "problems": self.problems,
            "admissible": self.admissible,
            "empty": self.empty,
        }


def gp_stem(name: str) -> str:
    """The GP node name of an operator without its version suffix."""
    return "".join(part.capitalize() for part in name.split("_"))


def shared_stems() -> set[str]:
    from lpstgp.operators.registry import discover

    return {s.gp_name.rsplit("_v", 1)[0] for s in discover().domain("data", "core")}


def _meta(path: Path, job: Path) -> dict[str, Any]:
    return execute.run("meta", path, job, worker="lpstgp.authoring.worker")


def read_patch(
    folder: Path,
    arm: str,
    state: LibraryState,
    initial: Mapping[str, str],
    initial_sha: Mapping[str, str],
    current: Mapping[str, Mapping],
    previous: Mapping[str, Mapping] | None,
    used_names: Sequence[str],
    work: Path,
    dev=None,
    gates: bool = True,
) -> Patch:
    """Classify the folder's changes and apply gates 1-2 (gate 1 only if ``gates``)."""
    patch = Patch()
    by_name = state.by_name()
    # Names are compared as the GP sees them (``toy_a`` and ``toy__a`` are both ``ToyA``), against
    # every name the arm's lineage has used and the shared core's and data terminals' (D-074).
    taken = {gp_stem(n) for n in (*by_name, *used_names)} | shared_stems()
    files = sorted(p for p in folder.glob("*.py") if p.name != API_FILE)
    present = {p.name for p in files}
    for fname, name in initial.items():
        if fname not in present:
            patch.prunes.append(name)  # a deleted file counts as emptied
    declared_kinds: dict[str, tuple] = {}
    for path in files:
        if path.name in initial:
            name = initial[path.name]
            if blank(path):
                patch.prunes.append(name)
                continue
            if sha(path) == initial_sha[path.name]:
                continue
            kind = "refine"
        else:
            if blank(path):
                continue
            name = None
            kind = "grow"
        meta = _meta(path, work / "meta" / path.stem)
        if not meta.get("ok"):
            patch.problems.append(f"{path.name}: {meta.get('error')}")
            continue
        op = meta["operator"]
        row = {"file": path.name, "sha256": sha(path), "operator": op}
        if kind == "refine":
            if op["name"] != name:
                patch.problems.append(
                    f"{path.name}: defines {op['name']}, not {name}; to add an operator, "
                    "write a new file"
                )
                continue
            row["parent"] = by_name[name].key
            row["domain"] = by_name[name].domain
            patch.refines.append(row)
        else:
            domain = declared_domain(path)
            if domain not in DOMAINS:
                patch.problems.append(
                    f'{path.name}: set DOMAIN = "<domain>" to one of {", ".join(DOMAINS)}'
                )
            if gp_stem(op["name"]) in taken:
                patch.problems.append(
                    f"{path.name}: the name {op['name']} is, or was, in the library (or matches "
                    "one of its node names); choose a new name"
                )
            row["domain"] = domain
            patch.grows.append(row)
        for p in op["params"].values():
            if p["kind"].startswith("Llm"):
                declared_kinds.setdefault(p["kind"], tuple(p["grid"]))
                if declared_kinds[p["kind"]] != tuple(p["grid"]):
                    patch.problems.append(f"{path.name}: kind {p['kind'][3:]} has two grids")
        if gates:
            _gate_one(path, work / path.stem, dev, row, patch)
    stems = [gp_stem(r["operator"]["name"]) for r in patch.grows]
    if len(stems) != len(set(stems)):
        patch.problems.append("two new files define the same operator name (or node name)")
    _gate_two(arm, state, patch, current, previous)
    return patch


def _gate_one(path: Path, work: Path, dev, row: dict, patch: Patch) -> None:
    gates = execute.run(
        "gates", path, work / "gates", inputs_path=dev.inputs_path if dev else None,
        worker="lpstgp.authoring.worker",
    )  # fmt: skip
    hashes = [
        execute.run(
            "hash", path, work / f"hash{t}", worker="lpstgp.authoring.worker", threads=t
        ).get("hash")
        for t in (1, 4)
    ]
    row["gates_passed"] = bool(gates.get("passed"))
    row["cross_process_deterministic"] = hashes[0] is not None and hashes[0] == hashes[1]
    if not row["gates_passed"]:
        failures = [r["check"] for r in gates.get("results", []) if not r["passed"]]
        patch.problems.append(
            f"{path.name}: fails check ({', '.join(failures) or gates.get('error')})"
        )
    if not row["cross_process_deterministic"]:
        patch.problems.append(f"{path.name}: output differs across processes or thread counts")


def _gate_two(
    arm: str,
    state: LibraryState,
    patch: Patch,
    current: Mapping[str, Mapping],
    previous: Mapping[str, Mapping] | None,
) -> None:
    bounds = BOUNDS[arm]
    for kind, items in (("grow", patch.grows), ("refine", patch.refines), ("prune", patch.prunes)):
        if len(items) > bounds[kind]:
            what = "is not allowed" if bounds[kind] == 0 else f"is limited to {bounds[kind]}"
            patch.problems.append(f"{len(items)} {kind}(s): {kind} {what} per cycle for this arm")
    by_name = state.by_name()
    for name in patch.prunes:
        key = by_name[name].key
        if not evidence.prunable(key, current, previous):
            patch.problems.append(
                f"prune of {name}: only operators marked prunable in the evidence table may be "
                "pruned (bottom quarter of the library by both usage and contribution in this "
                "cycle and the previous one)"
            )
    size = len(state.entries) + len(patch.grows) - len(patch.prunes)
    if size > LIBRARY_CAP:
        patch.problems.append(f"the library would hold {size} operators; the cap is {LIBRARY_CAP}")


def apply(
    state: LibraryState, patch: Patch, folder: Path, entered: str, provenance: Mapping[str, str]
) -> tuple[LibraryState, dict[str, Path]]:
    """The patched state and the source file of each new entry (an admissible patch only)."""
    if not patch.admissible:
        raise ValueError("an inadmissible patch cannot be applied")
    by_name = state.by_name()
    add, sources = [], {}
    for row in patch.refines:
        old = by_name[row["operator"]["name"]]
        add.append(
            Entry(
                old.name,
                old.version + 1,
                old.domain,
                row["sha256"],
                dict(provenance),
                entered,
                old.key,
            )
        )
    for row in patch.grows:
        add.append(
            Entry(
                row["operator"]["name"], 1, row["domain"], row["sha256"], dict(provenance), entered
            )
        )
    for e, row in zip(add, [*patch.refines, *patch.grows], strict=True):
        sources[e.key] = folder / row["file"]
    remove = [r["operator"]["name"] for r in patch.refines] + list(patch.prunes)
    # Which names an arm has retired is a property of its lineage, not of a library state: two
    # lineages can reach one state (D-074). The cycle derives it from the cycle records.
    return state.with_changes(remove, add), sources
