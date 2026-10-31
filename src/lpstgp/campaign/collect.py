"""Collect a campaign's records into one table (``runs.parquet``); refuse mixed digests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from lpstgp.campaign.execute import load_plan


class MixedDigestsError(RuntimeError):
    """Records were produced under different settings or configurations than the plan."""


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


def collect(plan_path: Path) -> pd.DataFrame:
    plan = load_plan(plan_path)
    root = Path(plan_path).parent
    rows = []
    for path in sorted(root.glob("tier*/records/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        meta = record.get("campaign", {})
        if meta.get("campaign") != plan["campaign"]:
            continue
        config = plan["configs"].get(meta.get("config"), {})
        if meta.get("settings_digest") != plan["settings_digest"] or meta.get(
            "config_digest"
        ) != config.get("digest"):
            raise MixedDigestsError(f"{path.name} was produced under other settings/configuration")
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
