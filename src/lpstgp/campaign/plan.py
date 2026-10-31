"""Campaign plans: tasks with ids and paired seeds, plus frozen digests of what they depend on."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpstgp.config import REPO_ROOT, Paths
from lpstgp.data.tier_a import git_revision
from lpstgp.freeze import digest
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.run import GPConfig
from lpstgp.operators.registry import LOCK_FILE as OPERATOR_LOCK
from lpstgp.runner import configs_from_settings
from lpstgp.strategies.registry import LOCK_FILE as STRATEGY_LOCK

PLAN_SCHEMA = "lpstgp.campaign/1"
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

    def resolved(self, settings: Mapping[str, Any]) -> tuple[GPConfig, FitnessConfig]:
        gp_cfg, fit_cfg = configs_from_settings(settings, **self.gp)
        return gp_cfg, replace(fit_cfg, **self.fitness)

    def digest(self, settings: Mapping[str, Any]) -> str:
        gp_cfg, fit_cfg = self.resolved(settings)
        lock = STRATEGY_LOCK if self.library.startswith("s2") else OPERATOR_LOCK
        return digest(
            {
                "library": self.library,
                "kind": self.kind,
                "gp": asdict(gp_cfg) if self.kind == "gp" else {},
                "fitness": asdict(fit_cfg),
                "lock": _file_digest(lock),
            }
        )


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def data_digest(paths: Paths, instruments: Sequence[str], tier: str = "A") -> dict[str, str]:
    processed = paths.tier_dir(tier) / "processed"
    return {name: _file_digest(processed / f"{name}.parquet") for name in sorted(instruments)}


def settings_digest(settings: Mapping[str, Any]) -> str:
    return digest(json.loads(json.dumps(settings, default=str)))


def write_plan(
    name: str,
    configs: Sequence[Config],
    cells: Sequence[tuple[tuple[str, ...], str]],
    runs: int,
    paths: Paths,
    settings: Mapping[str, Any],
    register: Path | None = REGISTER,
) -> Path:
    """Tasks = configs x cells (instrument set, period) x runs; select configs get one run."""
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
        "configs": {c.name: {**asdict(c), "digest": c.digest(settings)} for c in configs},
        "tasks": tasks,
    }
    out = paths.results_dir / "campaigns" / name / "tasks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=1, default=str) + "\n", encoding="utf-8")
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
