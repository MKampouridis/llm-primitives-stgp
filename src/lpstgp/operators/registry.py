"""Discovery of operator and terminal contracts, named libraries, and the version lock.

Every module under ``lpstgp.operators.<domain>`` defines ``SPEC`` (one OperatorSpec) or
``TERMINALS`` (a tuple of TerminalSpecs). ``registry.lock.toml`` stores, per contract key, the
sha256 of its module, the lpstgp helper modules it imports (transitively, excluding the metadata
modules ``types`` and ``contract``) and a canonical fingerprint of its semantic contract (types,
parameter grids, lookbacks, missing-data policy, invariances, bins). Once a key is locked none of
these may change: a modification must be added as a new version.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import pkgutil
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import lpstgp
from lpstgp.operators.contract import CROSS_DOMAINS, OperatorSpec, TerminalSpec

PACKAGE_ROOT = Path(lpstgp.__file__).resolve().parent
OPERATORS_DIR = PACKAGE_ROOT / "operators"
LOCK_FILE = OPERATORS_DIR / "registry.lock.toml"
INFRASTRUCTURE = ("contract", "registry", "catalogue")
# Metadata modules: their text does not determine any computation, so they are not hashed.
# (Semantic content they define for a contract is hashed via `fingerprint` instead.)
UNHASHED = ("lpstgp.types", "lpstgp.operators.contract")

# Named primitive sets. "seed" is the arm-6 library; "conventional" the GP-TA/DC baseline set.
LIBRARIES: dict[str, dict[str, tuple[str, ...]]] = {
    "seed": {"domains": ("data", "core", *CROSS_DOMAINS)},
    "conventional": {"domains": ("data", "core", "technical", "directional_change")},
    "technical": {"domains": ("data", "core", "technical")},  # GP-TA baseline (H2b), WP2
    "seed+conventional": {
        "domains": ("data", "core", *CROSS_DOMAINS, "technical", "directional_change")
    },
}


@dataclass(frozen=True)
class Registry:
    operators: dict[str, OperatorSpec]
    terminals: dict[str, TerminalSpec]
    modules: dict[str, str]  # contract key -> module name

    def all(self) -> dict[str, OperatorSpec | TerminalSpec]:
        return {**self.terminals, **self.operators}

    def domain(self, *domains: str) -> list[OperatorSpec | TerminalSpec]:
        return [s for s in self.all().values() if s.domain in domains]

    def library(self, name: str) -> list[OperatorSpec | TerminalSpec]:
        return self.domain(*LIBRARIES[name]["domains"])


def _iter_modules() -> Iterable[str]:
    for info in pkgutil.walk_packages([str(OPERATORS_DIR)], prefix="lpstgp.operators."):
        leaf = info.name.rsplit(".", 1)[-1]
        if not info.ispkg and not leaf.startswith("_") and leaf not in INFRASTRUCTURE:
            yield info.name


@cache
def discover() -> Registry:
    operators: dict[str, OperatorSpec] = {}
    terminals: dict[str, TerminalSpec] = {}
    modules: dict[str, str] = {}
    gp_names: set[str] = set()
    for name in sorted(_iter_modules()):
        module = importlib.import_module(name)
        specs = []
        if hasattr(module, "SPEC"):
            specs.append(module.SPEC)
        specs.extend(getattr(module, "TERMINALS", ()))
        for spec in specs:
            if spec.key in modules or spec.gp_name in gp_names:
                raise ValueError(f"duplicate contract {spec.key} in {name}")
            modules[spec.key] = name
            gp_names.add(spec.gp_name)
            if isinstance(spec, OperatorSpec):
                operators[spec.key] = spec
            else:
                terminals[spec.key] = spec
    return Registry(operators, terminals, modules)


def module_path(module: str) -> Path:
    return PACKAGE_ROOT.parent / Path(*module.split(".")).with_suffix(".py")


def _lpstgp_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("lpstgp"):
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("lpstgp"))
    return found


def dependency_files(module: str) -> list[Path]:
    """The module's file plus the lpstgp modules it imports, transitively (metadata modules excluded)."""
    seen: dict[str, Path] = {}
    stack = [module]
    while stack:
        current = stack.pop()
        if current in seen or current in UNHASHED:
            continue
        path = module_path(current)
        if not path.is_file():  # a package: its __init__
            path = PACKAGE_ROOT.parent / Path(*current.split(".")) / "__init__.py"
        if not path.is_file():
            continue
        seen[current] = path
        stack.extend(_lpstgp_imports(path))
    return [seen[m] for m in sorted(seen)]


def fingerprint(spec: OperatorSpec | TerminalSpec) -> str:
    """Canonical text of everything in a contract that changes what it computes or accepts."""
    from lpstgp.types import BIN_EDGES, N_BINS

    parts = [
        spec.key,
        spec.output.__name__,
        spec.missing.value,
        spec.memory.value,
        str(spec.size_weight),
    ]
    parts.append(f"bins={N_BINS}:{','.join(f'{e:.17g}' for e in BIN_EDGES)}")
    if isinstance(spec, OperatorSpec):
        parts.append(",".join(t.__name__ for t in spec.inputs))
        parts.append(";".join(f"{p.name}:{p.kind.__name__}:{p.grid}" for p in spec.params))
        parts.append(f"{spec.min_valid:.17g}|{','.join(spec.invariances)}|{spec.tolerance:.17g}")
        if spec.params:
            extremes = [
                {p.name: min(p.grid) for p in spec.params},
                {p.name: max(p.grid) for p in spec.params},
            ]
        else:
            extremes = [{}]
        parts.append(",".join(str(spec.lookback_for(e)) for e in extremes))
    else:
        parts.append(f"lookback={spec.lookback}|{spec.tolerance:.17g}")
    return "\n".join(parts)


def contract_hash(key: str) -> str:
    registry = discover()
    digest = hashlib.sha256()
    for path in dependency_files(registry.modules[key]):
        digest.update(str(path.relative_to(PACKAGE_ROOT.parent)).encode())
        digest.update(path.read_bytes())
    digest.update(fingerprint(registry.all()[key]).encode())
    return digest.hexdigest()


def read_lock() -> dict[str, str]:
    if not LOCK_FILE.is_file():
        return {}
    return dict(tomllib.loads(LOCK_FILE.read_text(encoding="utf-8")).get("contracts", {}))


def write_lock(entries: dict[str, str]) -> None:
    lines = [
        "# Version lock: sha256 of each contract's code (module + helper modules) and its fingerprint.",
        "# Locked entries are immutable; a modified implementation must be added as a new version.",
        "# Regenerate only with: uv run python scripts/update_lock.py",
        "",
        "[contracts]",
    ]
    lines += [f'"{key}" = "{entries[key]}"' for key in sorted(entries)]
    LOCK_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def lock_status() -> tuple[list[str], list[str]]:
    """``(changed, unlocked)`` contract keys relative to the lock file."""
    registry = discover()
    locked = read_lock()
    changed, unlocked = [], []
    for key in sorted(registry.modules):
        current = contract_hash(key)
        if key not in locked:
            unlocked.append(key)
        elif locked[key] != current:
            changed.append(key)
    return changed, unlocked
