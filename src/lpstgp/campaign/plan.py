"""Campaign plans: tasks with ids and paired seeds, plus frozen digests of what they depend on."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from lpstgp.config import REPO_ROOT, Paths
from lpstgp.data.tier_a import git_revision
from lpstgp.freeze import digest
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.run import GPConfig
from lpstgp.operators.registry import LOCK_FILE as OPERATOR_LOCK
from lpstgp.runner import configs_from_settings, write_atomic
from lpstgp.strategies.registry import LOCK_FILE as STRATEGY_LOCK

AUTHORED_LOCK = REPO_ROOT / "src" / "lpstgp" / "authoring" / "arm3.lock.toml"

PLAN_SCHEMA = "lpstgp.campaign/1"
# What makes two plans the same campaign (creation time and code revision do not).
PLAN_IDENTITY = (
    "schema", "campaign", "settings_digest", "data_digest", "source_digest", "configs", "tasks",
)  # fmt: skip
SOURCE_ROOT = REPO_ROOT / "src" / "lpstgp"


class PlanExistsError(RuntimeError):
    """A different plan already exists, with run records, under the same campaign name."""


REGISTER = REPO_ROOT / "reports" / "configuration_register.csv"


def run_seed(instruments: Sequence[str], period: str, run: int) -> int:
    """Seed of one run: depends on (instruments, period, run) only, never on the arm (pairing)."""
    text = f"{'+'.join(instruments)}|{period}|{run}"
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


@dataclass(frozen=True)
class Config:
    """One configuration (arm): a library plus GP and fitness settings."""

    name: str
    library: str
    kind: str = "gp"  # "gp" or "select" (arm 1)
    gp: Mapping[str, Any] = field(default_factory=dict)  # overrides of the settings' [gp]
    fitness: Mapping[str, Any] = field(default_factory=dict)  # overrides of [fitness]
    # Arm 5 (WP4): the period's admitted LLM rule pairs, placed first in every initial population.
    seed_rules: tuple[tuple[str, str], ...] = ()

    def resolved(self, settings: Mapping[str, Any]) -> tuple[GPConfig, FitnessConfig]:
        gp_cfg, fit_cfg = configs_from_settings(settings, **self.gp)
        return gp_cfg, replace(fit_cfg, **self.fitness)

    def digest(self, settings: Mapping[str, Any]) -> str:
        gp_cfg, fit_cfg = self.resolved(settings)
        uses_strategies = self.kind == "select" or self.library.startswith("s2")
        lock = STRATEGY_LOCK if uses_strategies else OPERATOR_LOCK
        payload = {
            "library": self.library,
            "kind": self.kind,
            "gp": asdict(gp_cfg) if self.kind == "gp" else {},
            "fitness": asdict(fit_cfg),
            "lock": _file_digest(lock),
        }
        if uses_strategies:  # arms 2a-2c also use core operators (logic, glue, data)
            payload["operator_lock"] = _file_digest(OPERATOR_LOCK)
        # Added keys only when used, so every earlier configuration keeps its digest (D-084).
        if self.library == "arm3" or self.library.startswith("state:"):
            payload["authored_lock"] = _file_digest(AUTHORED_LOCK)  # state ids are content hashes
        if self.seed_rules:
            payload["seed_rules"] = [list(r) for r in self.seed_rules]
        return digest(payload)


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


# Build provenance in a processed file's metadata: it changes on every rebuild or download and
# does not change a row (the rows and the rest of the metadata are digested).
PROVENANCE_META = ("built_at_utc", "code_version", "raw_files", "design_end")


@cache
def digest_horizon() -> date:
    """Data are digested up to (excluding) PC's test start: every row a modelling read or a
    P01..P18 test read can reach. Bars added later (PC's test year, D-075) leave every digest of
    WP3 and WP4 unchanged; any change to an earlier row or to the metadata changes it (D-087)."""
    from lpstgp.config import load_settings
    from lpstgp.splits import post_cutoff_period

    settings = load_settings()
    pc = post_cutoff_period(settings)
    return pc.test_start if pc is not None else settings["leakage"]["max_horizon"]


def rows_digest(path: Path, horizon: date | None = None) -> str:
    """Digest of a processed file's rows before ``horizon`` and its metadata (less provenance)."""
    if not path.exists():
        return ""
    horizon = horizon or digest_horizon()
    table = pq.read_table(path)
    raw = (table.schema.metadata or {}).get(b"lpstgp")
    meta = json.loads(raw) if raw else {}
    frame = table.to_pandas(date_as_object=False)
    frame = frame[frame["date"].to_numpy().astype("datetime64[D]") < np.datetime64(horizon)]
    h = hashlib.sha256()
    h.update(json.dumps({k: v for k, v in meta.items() if k not in PROVENANCE_META},
                        sort_keys=True, default=str).encode())  # fmt: skip
    h.update(json.dumps([(c, str(frame[c].dtype)) for c in frame.columns]).encode())
    h.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    return h.hexdigest()


def data_digest(paths: Paths, instruments: Sequence[str], tier: str = "A") -> dict[str, str]:
    processed = paths.tier_dir(tier) / "processed"
    return {name: rows_digest(processed / f"{name}.parquet") for name in sorted(instruments)}


def source_digest(root: Path = SOURCE_ROOT) -> str:
    """Digest of the package's source and resources (paths and contents): the code that makes
    results, and the prompt templates, locks and frozen files it reads (D-081; Python files only
    before). Any change to it, however small, makes a campaign's plan and records stale (D-049),
    so a campaign never mixes results from different code. Byte-identical on the Mac and CERES.
    """
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        h.update(path.relative_to(root).as_posix().encode() + b"\0")
        h.update(path.read_bytes() + b"\0")
    return h.hexdigest()


def tier_digest(paths: Paths, tier: str = "A") -> str:
    """Digest of every processed file of a tier: the data any tool may read, including the
    development cohort of the LLM's ``describe`` tool, not only a campaign's instruments (D-081)."""
    processed = paths.tier_dir(tier) / "processed"
    return digest({p.name: rows_digest(p) for p in sorted(processed.glob("*.parquet"))})


# Settings that guard or fetch data but do not change a result: ``[leakage]`` (refuses reads
# only; PC's read raises its cap) and ``[data]`` (download range; the rows are digested). Left out
# so that PC's test read does not invalidate PC's own records (D-087).
NOT_RESULT_SETTINGS = ("leakage", "data")


def settings_digest(settings: Mapping[str, Any]) -> str:
    kept = {k: v for k, v in settings.items() if k not in NOT_RESULT_SETTINGS}
    return digest(json.loads(json.dumps(kept, default=str)))


def write_plan(
    name: str,
    configs: Sequence[Config],
    cells: Sequence[tuple[tuple[str, ...], str]],
    runs: int,
    paths: Paths,
    settings: Mapping[str, Any],
    register: Path | None = REGISTER,
    record_format: str = "json",
) -> Path:
    """Tasks = configs x cells (instrument set, period) x runs; select configs get one run.
    ``record_format="json.gz"`` (WP4, D-085) writes gzip-compressed records."""
    tasks = []
    for config in configs:
        n_runs = 1 if config.kind == "select" else runs
        for instruments, period in cells:
            for run in range(1, n_runs + 1):
                tasks.append(
                    {
                        "id": f"{config.name}/{period}/{'+'.join(instruments)}/r{run:02d}",
                        "config": config.name,
                        "instruments": list(instruments),
                        "period": period,
                        "run": run,
                        "seed": run_seed(instruments, period, run),
                    }
                )
    instruments = sorted({i for cell, _ in cells for i in cell})
    plan = {
        "schema": PLAN_SCHEMA,
        "campaign": name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_version": git_revision(),
        "settings_digest": settings_digest(settings),
        "data_digest": data_digest(paths, instruments),
        "source_digest": source_digest(),
        "configs": {c.name: {**asdict(c), "digest": c.digest(settings)} for c in configs},
        "tasks": tasks,
    }
    if record_format != "json":
        if record_format != "json.gz":
            raise ValueError(f"unknown record format {record_format}")
        plan["record_format"] = record_format
    plan = json.loads(json.dumps(plan, default=str))  # as stored, so plans compare exactly
    out = paths.results_dir / "campaigns" / name / "tasks.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    changed = [k for k in PLAN_IDENTITY if old is not None and old.get(k) != plan[k]]
    if old is not None and not changed:
        plan = old  # the same plan: left untouched (cluster jobs may be reading it)
    else:
        if changed and any(any(out.parent.glob(f"tier*/*/*.{ext}")) for ext in ("json", "json.gz")):
            raise PlanExistsError(
                f"{out} has run records and differs from the plan now requested in "
                f"{', '.join(changed)}; move the campaign folder aside or use a new name"
            )
        write_atomic(out, json.dumps(plan, indent=1) + "\n")
    if register is not None:
        register_configs(register, name, plan["configs"])
    return out


def register_configs(register: Path, campaign: str, configs: Mapping[str, Mapping]) -> None:
    """Append each (configuration, digest) once: the trial count for the Deflated Sharpe Ratio."""
    seen = set()
    if register.exists():
        with register.open(newline="", encoding="utf-8") as handle:
            seen = {(row["config"], row["digest"]) for row in csv.DictReader(handle)}
    new = [(n, c) for n, c in configs.items() if (n, c["digest"]) not in seen]
    if not new:
        return
    write_header = not register.exists()
    register.parent.mkdir(parents=True, exist_ok=True)
    with register.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(["first_used_utc", "campaign", "config", "library", "kind", "digest"])
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for name, config in new:
            writer.writerow(
                [now, campaign, name, config["library"], config["kind"], config["digest"]]
            )
