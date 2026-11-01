"""Collect a campaign's records into one table (``runs.parquet``); refuse mixed digests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from lpstgp.campaign.execute import load_plan, plan_records
from lpstgp.config import Paths, load_paths, load_settings


def _gp_row(record: dict) -> dict:
    best = record["hall_of_fame"][record["selected"]]
    val = best.get("validation", {})
    val_sharpes = [c.get("sharpe", 0.0) for c in val.get("instruments", {}).values()]
    return {
        "entry": best["entry_str"],
        "exit": best["exit_str"],
        "size_w": best["size_w"],
        "lookback": best["lookback"],
        "fit_fitness": best["fit"]["fitness"],
        "validation_fitness": val.get("fitness", np.nan),
        "validation_sharpe": float(np.mean(val_sharpes)) if val_sharpes else np.nan,
        "requested_evaluations": record["budget"]["requested_evaluations"],
        "unique_evaluations": record["budget"]["unique_evaluations"],
        "wall_clock_s": record.get("wall_clock_s", np.nan),
        "peak_rss_mb": record.get("peak_rss_mb", np.nan),
    }


def collect(plan_path: Path, paths: Paths | None = None, settings=None) -> pd.DataFrame:
    """One row per task (arm 1: per instrument), from the plan's own task list only.

    Records go through ``plan_records``: the plan's settings, configuration and data digests must
    match the current ones, and every task must have one complete record; stray, stale or
    duplicate files are never read.
    """
    plan = load_plan(plan_path)
    root = Path(plan_path).parent
    paths = paths or load_paths()
    settings = settings or load_settings()
    rows = []
    for record in plan_records(plan_path, paths, settings):
        meta = record["campaign"]
        config = plan["configs"][meta["config"]]
        base = {
            "task_id": meta["task_id"],
            "config": meta["config"],
            "library": config["library"],
            "kind": config["kind"],
            "period": record["period"]["id"],
            "instruments": "+".join(record["instruments"]),
            "run": int(meta["run"]),
            "code_version": record.get("code_version", ""),
        }
        if config["kind"] == "select":
            for instrument, result in record["selection"].items():
                rows.append(
                    {
                        **base,
                        "instruments": instrument,
                        "entry": result["selected"],
                        "exit": result["selected"],
                        "validation_fitness": result["validation"][result["selected"]],
                        "fit_fitness": result["fit"][result["selected"]],
                    }
                )
        else:
            rows.append({**base, "seed": record["seed"], **_gp_row(record)})
    table = pd.DataFrame(rows)
    if len(table):
        table = table.sort_values(["config", "period", "instruments", "run"]).reset_index(drop=True)
        table.to_parquet(root / "runs.parquet", index=False)
    return table
