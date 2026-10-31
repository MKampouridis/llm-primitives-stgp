"""Execute a campaign plan: verify its digests, skip finished tasks, run the rest."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpstgp.backtest.costs import from_meta
from lpstgp.campaign.plan import PLAN_SCHEMA, Config, data_digest, settings_digest
from lpstgp.config import Paths
from lpstgp.data.store import modelling_store
from lpstgp.data.tier_a import git_revision
from lpstgp.runner import RunTask, record_path, run_many, write_atomic
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, all_periods
from lpstgp.strategies import selection
from lpstgp.strategies.registry import load_frozen, lock_digest


class PlanMismatchError(RuntimeError):
    """The settings, data or libraries changed since the plan was written."""


def load_plan(path: Path) -> dict:
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"{path} is not a campaign plan")
    return plan


def _config(plan: Mapping, name: str) -> Config:
    c = plan["configs"][name]
    return Config(c["name"], c["library"], c["kind"], c["gp"], c["fitness"])


def verify(plan: Mapping, paths: Paths, settings: Mapping[str, Any]) -> list[str]:
    problems = []
    if settings_digest(settings) != plan["settings_digest"]:
        problems.append("settings changed since the plan was written")
    if data_digest(paths, plan["data_digest"]) != plan["data_digest"]:
        problems.append("data files changed since the plan was written")
    for name, config in plan["configs"].items():
        if _config(plan, name).digest(settings) != config["digest"]:
            problems.append(f"configuration {name} (or its library lock) changed")
    return problems


def _meta(plan: Mapping, task: Mapping) -> tuple[tuple[str, str], ...]:
    return (
        ("campaign", plan["campaign"]),
        ("task_id", task["id"]),
        ("config", task["config"]),
        ("run", str(task["run"])),
        ("config_digest", plan["configs"][task["config"]]["digest"]),
        ("settings_digest", plan["settings_digest"]),
    )


def run_task(plan: Mapping, task: Mapping, settings: Mapping[str, Any]) -> RunTask:
    gp_cfg, fit_cfg = _config(plan, task["config"]).resolved(settings)
    return RunTask(
        experiment="records",
        library=plan["configs"][task["config"]]["library"],
        instruments=tuple(task["instruments"]),
        period=task["period"],
        seed=task["seed"],
        gp=gp_cfg,
        fitness=fit_cfg,
        campaign=_meta(plan, task),
    )


def is_complete(path: Path, run: RunTask) -> bool:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return record.get("campaign") == dict(run.campaign) and (
        "hall_of_fame" in record or "selection" in record
    )


def execute_select(run: RunTask, paths: Paths, settings: Mapping[str, Any], out_root: Path) -> dict:
    """Arm 1 for one (instrument set, period): deterministic, runs in-process."""
    started = time.perf_counter()
    period = all_periods(settings)[run.period]
    lmax = settings["splits"]["lookback_max_bars"]
    store = modelling_store(paths.tier_dir(run.tier), settings)
    fit_box = Sandbox.open(store, period, Stage.FIT, run.instruments, lmax)
    val_box = Sandbox.open(store, period, Stage.VALIDATE, run.instruments, lmax)
    del store
    costs = {name: from_meta(fit_box[name].meta) for name in run.instruments}
    frozen = load_frozen()
    record = {
        "schema": 1,
        "kind": "select",
        "run_id": run.name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_version": git_revision(),
        "campaign": dict(run.campaign),
        "library": {"name": run.library, "strategies_lock": lock_digest()},
        "instruments": list(run.instruments),
        "period": {k: str(v) for k, v in asdict(period).items()},
        "fitness_config": asdict(run.fitness),
        "sandbox_access": [
            {k: str(v) for k, v in asdict(r).items()}
            for r in fit_box.access_log + val_box.access_log
        ],
        "selection": selection.select(frozen, fit_box, val_box, costs, run.fitness),
        "wall_clock_s": time.perf_counter() - started,
    }
    write_atomic(record_path(out_root, run), json.dumps(record, default=str))
    return record


def execute_plan(
    plan_path: Path, paths: Paths, settings: Mapping[str, Any], workers: int = 4
) -> dict[str, int]:
    plan = load_plan(plan_path)
    problems = verify(plan, paths, settings)
    if problems:
        raise PlanMismatchError("; ".join(problems))
    out_root = Path(plan_path).parent
    pending_gp, done, selected = [], 0, 0
    for task in plan["tasks"]:
        run = run_task(plan, task, settings)
        if is_complete(record_path(out_root, run), run):
            done += 1
        elif plan["configs"][task["config"]]["kind"] == "select":
            execute_select(run, paths, settings, out_root)
            selected += 1
        else:
            pending_gp.append(run)
    run_many(pending_gp, workers, out_root)
    return {"skipped": done, "selected": selected, "evolved": len(pending_gp)}
