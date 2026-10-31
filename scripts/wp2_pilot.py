"""WP2 milestones M3-M4 on the pilot periods (protocol §6-§8), step by step.

Usage: uv run python scripts/wp2_pilot.py STEP [--workers 6]

  calibrate     §6.1 equal-budget GP-parameter candidates (arms 2c and 6), PL1 training data
  budget-check  §6.2-6.3 every GP arm at the chosen parameters: budget unit and lambda rules
  gonogo        plan and run the go/no-go campaign (arms 1, 2a, 2b, 2c, 6, GP-TA; PL1 and PL2)
  freeze        write reports/wp2/freeze_manifest.json (commit it before `pilot-test`)
  pilot-test    §8 the one-time test-year evaluation, portfolios and the go/no-go decision

Results go to results/campaigns/<name>/ and reports/wp2/. No step reads any bar on or after
2008-07-01 (the settings' data cap); only `pilot-test` opens the pilot test years.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from lpstgp import calibration, pilot
from lpstgp.campaign.execute import execute_plan, load_plan
from lpstgp.campaign.plan import Config, settings_digest, write_plan
from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.data.store import modelling_store
from lpstgp.data.tier_a import git_revision
from lpstgp.freeze import FreezeManifest, write_manifest
from lpstgp.operators.registry import LOCK_FILE as OPERATOR_LOCK
from lpstgp.runner import configs_from_settings
from lpstgp.sandbox import Sandbox
from lpstgp.splits import pilot_periods
from lpstgp.strategies import registry

CALIBRATION_INSTRUMENTS = ("SPX", "NKY", "EURUSD", "USDJPY", "GOLD", "NATGAS")  # protocol §6.1
PILOT_INSTRUMENTS = (
    "SPX", "NDX", "SMI", "DAX", "CAC", "UKX", "NKY", "HSI", "KOSPI", "AS51",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "NATGAS", "GOLD", "SILVER", "COPPER",
)  # fmt: skip
GP_ARMS = {"2a": "s2a", "2b": "s2b", "2c": "s2c", "6": "seed", "TA": "technical"}
CAL_BUDGET = 50_000
REPORTS = REPO_ROOT / "reports" / "wp2"


def records(plan_path: Path) -> list[dict]:
    return [
        json.loads(p.read_text()) for p in sorted(plan_path.parent.glob("tier*/records/*.json"))
    ]


def chosen_parameters() -> dict:
    return json.loads((REPORTS / "calibration.json").read_text())


def step_calibrate(paths, settings, workers: int) -> None:
    configs = [
        Config(
            f"cal-{arm}-p{pop}-t{tour}",
            arm,
            gp={"population": pop, "generations": CAL_BUDGET // pop - 1, "tournament": tour},
        )
        for arm in ("s2c", "seed")
        for pop in (250, 500, 1000)
        for tour in (3, 5)
    ]
    cells = [((name,), "PL1") for name in CALIBRATION_INSTRUMENTS]
    plan = write_plan("wp2-calibration", configs, cells, 10, paths, settings)
    print(execute_plan(plan, paths, settings, workers))
    choice = calibration.choose_candidate(records(plan))
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "calibration.json").write_text(json.dumps(choice, indent=1))
    print(json.dumps({k: v for k, v in choice.items() if k != "table"}, indent=1))


def step_budget_check(paths, settings, workers: int) -> None:
    c = chosen_parameters()
    gp = {
        "population": c["population"],
        "generations": c["generations"],
        "tournament": c["tournament"],
    }
    configs = [Config(f"bud-{arm}", lib, gp=gp) for arm, lib in GP_ARMS.items()]
    cells = [((name,), "PL1") for name in CALIBRATION_INSTRUMENTS]
    plan = write_plan("wp2-budget-check", configs, cells, 3, paths, settings)
    print(execute_plan(plan, paths, settings, workers))
    recs = records(plan)
    out = {"budget_unit": calibration.budget_unit(recs), "lambda": calibration.lambda_check(recs)}
    (REPORTS / "budget_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def gonogo_configs() -> list[Config]:
    c = chosen_parameters()
    check = json.loads((REPORTS / "budget_check.json").read_text())
    gp = {
        "population": c["population"],
        "generations": c["generations"],
        "tournament": c["tournament"],
    }
    if check["budget_unit"]["unit"] == "unique":
        gp |= {
            "budget_unit": "unique",
            "max_unique_evaluations": c["requested_evaluations"],
            "generations": 100_000,
        }
    return [Config("arm1", "strategies", kind="select")] + [
        Config(f"arm{arm}", lib, gp=gp) for arm, lib in GP_ARMS.items()
    ]


def gonogo_plans(paths) -> list[Path]:
    return [
        paths.results_dir / "campaigns" / f"wp2-gonogo-{p}" / "tasks.json" for p in ("PL1", "PL2")
    ]


def step_gonogo(paths, settings, workers: int) -> None:
    for period, plan_path in zip(("PL1", "PL2"), gonogo_plans(paths), strict=True):
        if not plan_path.exists():
            cells = [((name,), period) for name in PILOT_INSTRUMENTS]
            write_plan(f"wp2-gonogo-{period}", gonogo_configs(), cells, 10, paths, settings)
        print(period, execute_plan(plan_path, paths, settings, workers))


def step_freeze(paths, settings) -> None:
    rules = {}
    context = {"settings_digest": settings_digest(settings), "code_version": git_revision()}
    context |= {
        "strategies_lock": registry.lock_digest(),
        "operator_lock": registry.file_hash(OPERATOR_LOCK),
    }
    for plan_path in gonogo_plans(paths):
        plan = load_plan(plan_path)
        recs = records(plan_path)
        if len(recs) != len(plan["tasks"]):
            raise SystemExit(f"{plan['campaign']}: {len(recs)} of {len(plan['tasks'])} tasks done")
        rules |= pilot.manifest_rules(recs)
        context[f"plan:{plan['campaign']}"] = plan["settings_digest"]
    path = REPORTS / "freeze_manifest.json"
    write_manifest(path, rules, context)
    print(f"{len(rules)} rules frozen in {path}; commit it before `pilot-test`")


def step_pilot_test(paths, settings) -> None:
    manifest = FreezeManifest.load_committed(REPORTS / "freeze_manifest.json")
    _, cfg = configs_from_settings(settings)
    frozen = registry.load_frozen()
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    yearly: dict[str, dict] = {}
    raw: dict[str, np.ndarray] = {}
    for period, plan_path in zip(pilot_periods(settings), gonogo_plans(paths), strict=True):
        box = Sandbox.open_pilot_test(
            store,
            period,
            PILOT_INSTRUMENTS,
            lmax,
            pilot_periods=pilot_periods(settings),
            manifest=manifest,
        )
        runs: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for record in records(plan_path):
            task = record["campaign"]["task_id"]
            manifest.require(task, pilot.rule_hash(record))
            arm = task.split("/")[0].removeprefix("arm")
            for name, series in pilot.evaluate_on_test(
                record, _subset(box, record["instruments"]), cfg, frozen
            ).items():
                runs[arm][name].append(series)
        for name, series in pilot.buy_and_hold(box, cfg).items():
            runs["BH"][name].append(series)
        yearly[period.id] = {arm: pilot.portfolio(by_inst) for arm, by_inst in runs.items()}
        for arm, (dates, values) in yearly[period.id].items():
            raw[f"{period.id}:{arm}:dates"], raw[f"{period.id}:{arm}:returns"] = (
                dates.astype("datetime64[D]").astype(str),
                values,
            )
    pooled = {
        arm: (
            np.concatenate([yearly[p][arm][0] for p in yearly]),
            np.concatenate([yearly[p][arm][1] for p in yearly]),
        )
        for arm in yearly["PL1"]
    }
    result = pilot.go_no_go(pooled, yearly)
    result["manifest_commit"] = manifest.commit
    (REPORTS / "pilot_go_no_go.json").write_text(json.dumps(result, indent=1, default=float))
    np.savez_compressed(paths.results_dir / "campaigns" / "wp2-pilot-test-portfolios.npz", **raw)
    print(json.dumps({k: result[k] for k in ("decision", "difference", "pooled_sharpe")}, indent=1))


def _subset(box: Sandbox, instruments) -> Sandbox:
    """The test sandbox restricted to a task's instruments (no new data read)."""
    from dataclasses import replace
    from types import MappingProxyType

    return replace(box, bars=MappingProxyType({k: box[k] for k in instruments}))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "step", choices=("calibrate", "budget-check", "gonogo", "freeze", "pilot-test")
    )
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    if args.step == "calibrate":
        step_calibrate(paths, settings, args.workers)
    elif args.step == "budget-check":
        step_budget_check(paths, settings, args.workers)
    elif args.step == "gonogo":
        step_gonogo(paths, settings, args.workers)
    elif args.step == "freeze":
        step_freeze(paths, settings)
    else:
        step_pilot_test(paths, settings)


if __name__ == "__main__":
    main()
