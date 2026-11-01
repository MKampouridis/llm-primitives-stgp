"""WP2 milestones M3-M4 on the pilot periods (protocol §6-§8), step by step.

Usage: uv run python scripts/wp2_pilot.py STEP [--workers 6] [--mode all|plan|report]

  portability   two runs to check that CERES and this machine give identical records
  calibrate     §6.1 equal-budget GP-parameter candidates (arms 2c and 6), PL1 training data
  budget-check  §6.2-6.3 every GP arm at the chosen parameters: budget unit and lambda rules
  gonogo        plan and run the go/no-go campaign (arms 1, 2a, 2b, 2c, 6, GP-TA; PL1 and PL2)
  freeze        write reports/wp2/freeze_manifest.json (commit it before `pilot-test`)
  pilot-test    §8 the one-time test-year evaluation, portfolios and the go/no-go decision

--mode (calibrate, budget-check, gonogo): `all` (default) plans, runs on this machine and reports;
`plan` only writes the campaign plan, for a cluster (scripts/campaign_tasks.py, docs/CERES.md);
`report` reports on a plan whose tasks are all complete (records copied back from the cluster).

Results go to results/campaigns/<name>/ and reports/wp2/. No step reads any bar on or after
2008-07-01 (the settings' data cap); only `pilot-test` opens the pilot test years.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from lpstgp import calibration, pilot
from lpstgp.campaign.execute import execute_plan, load_plan, plan_records, progress
from lpstgp.campaign.plan import Config, data_digest, settings_digest, write_plan
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
UNIQUE_CEILING = 10  # unique budget: at most this many times the calibrated generations
REPORTS = REPO_ROOT / "reports" / "wp2"


def prepare(name, configs, cells, runs, paths, settings, workers: int, mode: str) -> Path | None:
    """Plan (unless reporting), run here (mode all) and return the plan once every task is done."""
    plan_path = paths.results_dir / "campaigns" / name / "tasks.json"
    if mode != "report":
        plan_path = write_plan(name, configs, cells, runs, paths, settings)
    if mode == "all":
        print(execute_plan(plan_path, paths, settings, workers))
    status = progress(plan_path, settings)
    if mode == "plan":
        print(f"{name}: {status['tasks']} tasks; run them with scripts/ceres/tasks.sge")
        return None
    if status["complete"] != status["tasks"]:
        raise SystemExit(f"{name}: {status['complete']} of {status['tasks']} tasks complete")
    return plan_path


def records(plan_path: Path) -> list[dict]:
    """Every task's complete, current record, in plan order (refuses if any is missing)."""
    return plan_records(plan_path, load_paths(), load_settings())


def chosen_parameters() -> dict:
    return json.loads((REPORTS / "calibration.json").read_text())


def step_calibrate(paths, settings, workers: int, mode: str = "all") -> None:
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
    plan = prepare("wp2-calibration", configs, cells, 10, paths, settings, workers, mode)
    if plan is None:
        return
    choice = calibration.choose_candidate(records(plan))
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "calibration.json").write_text(json.dumps(choice, indent=1))
    lines = [
        "# WP2 calibration: GP parameters at equal budget (protocol §6.1)",
        "",
        f"Arms 2c and 6 pooled; {', '.join(CALIBRATION_INSTRUMENTS)}; PL1 training data only; "
        f"10 runs per arm and instrument; {CAL_BUDGET:,} requested evaluations per candidate.",
        "",
        "| population | tournament | runs | median validation F | median convergence gen | "
        "generations | evaluations |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {r['population']} | {r['tournament']} | {r['runs']} | {r['median_validation']:.4f} | "
        f"{r['median_convergence']:.0f} | {r['generations']} | {r['requested_evaluations']:,} |"
        for r in choice["table"]
    ]
    lines += [
        "",
        f"**Chosen:** population {choice['population']}, tournament {choice['tournament']}, "
        f"{choice['generations']} generations ({choice['requested_evaluations']:,} requested "
        f"evaluations): the cheapest candidate within {choice['tolerance']} of the best median "
        f"validation F ({choice['best_median_validation']:.4f}).",
    ]
    (REPORTS / "calibration.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in choice.items() if k != "table"}, indent=1))


def step_portability(paths, settings, workers: int, mode: str = "all") -> None:
    """Two calibration-size runs (arms 2c and 6, SPX, PL1) to compare machines (docs/CERES.md §5).

    Not a study campaign: its configurations are not entered in the trial register.
    """
    gp = {"population": 500, "generations": CAL_BUDGET // 500 - 1, "tournament": 3}
    configs = [Config(f"port-{arm}", arm, gp=gp) for arm in ("s2c", "seed")]
    plan = write_plan(
        "wp2-portability", configs, [(("SPX",), "PL1")], 1, paths, settings, register=None
    )
    if mode == "all":
        print(execute_plan(plan, paths, settings, workers))
    print(progress(plan, settings))


def step_budget_check(paths, settings, workers: int, mode: str = "all") -> None:
    c = chosen_parameters()
    gp = {
        "population": c["population"],
        "generations": c["generations"],
        "tournament": c["tournament"],
    }
    configs = [Config(f"bud-{arm}", lib, gp=gp) for arm, lib in GP_ARMS.items()]
    cells = [((name,), "PL1") for name in CALIBRATION_INSTRUMENTS]
    plan = prepare("wp2-budget-check", configs, cells, 3, paths, settings, workers, mode)
    if plan is None:
        return
    recs = records(plan)
    step1 = records(paths.results_dir / "campaigns" / "wp2-calibration" / "tasks.json")
    out = {
        "budget_unit": calibration.budget_unit(recs),
        "lambda": calibration.lambda_check(step1 + recs),  # §6.3: the runs of steps 1-2
    }
    (REPORTS / "budget_check.json").write_text(json.dumps(out, indent=1))
    timing = defaultdict(list)
    for r in recs:
        timing[r["library"]["name"]].append(r["timings"]["per_requested_evaluation_ms"])
    lines = [
        "# WP2 budget unit and fitness weights (protocol §6.2-6.3)",
        "",
        f"Every GP arm at the chosen parameters, 3 runs on {', '.join(CALIBRATION_INSTRUMENTS)} (PL1).",
        "",
        "| arm (library) | median unique share | ms per requested evaluation (median) |",
        "|---|---:|---:|",
    ]
    for arm, share in out["budget_unit"]["median_unique_share"].items():
        lines.append(f"| {arm} | {share:.3f} | {np.median(timing[arm]):.2f} |")
    lam = out["lambda"]
    lines += [
        "",
        f"Spread of unique shares: {out['budget_unit']['spread']:.2f}x -> budget unit "
        f"**{out['budget_unit']['unit']}** (rule: unique if > 2x).",
        f"Final rules of steps 1-2 ({lam['rules']} rule-instrument pairs) with no trade on "
        f"validation: {lam['no_trade_share']:.1%} (limit 25%; exceeded: "
        f"**{lam['no_trade_exceeded']}**, which calls for a recorded decision, D-047).",
        f"Median validation turnover {lam['median_turnover']:.1f} changes a year -> raise "
        f"lambda_turnover: **{lam['raise_lambda_turnover']}** (rule: > 50).",
    ]
    (REPORTS / "budget_check.md").write_text("\n".join(lines) + "\n")
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
            # Ceiling so that no run, and no arm, can run away (D-047); budget.cap_reached in
            # each record says which limit ended the run.
            "generations": UNIQUE_CEILING * c["generations"],
        }
    return [Config("arm1", "strategies", kind="select")] + [
        Config(f"arm{arm}", lib, gp=gp) for arm, lib in GP_ARMS.items()
    ]


def gonogo_plans(paths) -> list[Path]:
    return [
        paths.results_dir / "campaigns" / f"wp2-gonogo-{p}" / "tasks.json" for p in ("PL1", "PL2")
    ]


def step_gonogo(paths, settings, workers: int, mode: str = "all") -> None:
    for period, plan_path in zip(("PL1", "PL2"), gonogo_plans(paths), strict=True):
        if not plan_path.exists() and mode != "report":
            cells = [((name,), period) for name in PILOT_INSTRUMENTS]
            write_plan(f"wp2-gonogo-{period}", gonogo_configs(), cells, 10, paths, settings)
        if mode == "all":
            print(period, execute_plan(plan_path, paths, settings, workers))
        print(period, progress(plan_path, settings))


def frozen_context(paths, settings) -> dict:
    """Everything the frozen rules' test evaluation depends on besides the rules themselves."""
    context = {
        "settings_digest": settings_digest(settings),
        "strategies_lock": registry.lock_digest(),
        "operator_lock": registry.file_hash(OPERATOR_LOCK),
        "data_digest": data_digest(paths, PILOT_INSTRUMENTS),
    }
    for plan_path in gonogo_plans(paths):
        plan = load_plan(plan_path)
        context[f"plan:{plan['campaign']}"] = {
            "settings_digest": plan["settings_digest"],
            "configs": {k: c["digest"] for k, c in sorted(plan["configs"].items())},
            "tasks": len(plan["tasks"]),
        }
    return context


def source_changed_since(revision: str) -> list[str]:
    """Files under src/, scripts/ or config/ changed between ``revision`` and the working tree."""
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", revision, "--", "src", "scripts",
         "config"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return out.stdout.split()


def step_freeze(paths, settings) -> None:
    if source_changed_since("HEAD"):
        raise SystemExit("commit the code first: the manifest records the code revision")
    rules = {}
    for plan_path in gonogo_plans(paths):
        rules |= pilot.manifest_rules(records(plan_path))  # every task, complete and current
    context = frozen_context(paths, settings) | {"code_version": git_revision()}
    path = REPORTS / "freeze_manifest.json"
    write_manifest(path, rules, context)
    print(f"{len(rules)} rules frozen in {path}; commit it before `pilot-test`")


def step_pilot_test(paths, settings) -> None:
    out_json = REPORTS / "pilot_go_no_go.json"
    if out_json.exists():  # protocol §8: the test years are read once
        raise SystemExit(f"{out_json} exists: the pilot test years have already been read")
    manifest = FreezeManifest.load_committed(REPORTS / "freeze_manifest.json")
    frozen_code = manifest.context["code_version"]
    manifest.check_context(frozen_context(paths, settings) | {"code_version": frozen_code})
    if changed := source_changed_since(frozen_code):
        raise SystemExit(f"code changed since the freeze: {', '.join(changed)}")
    _, cfg = configs_from_settings(settings)
    frozen = registry.load_frozen()
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    yearly: dict[str, dict] = {}
    raw: dict[str, np.ndarray] = {}
    access: dict[str, list] = {}
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
        recs = records(plan_path)
        expected = {t for t in manifest.rules if t.split("/")[1] == period.id}
        if {r["campaign"]["task_id"] for r in recs} != expected:
            raise SystemExit(f"{period.id}: the records do not match the manifest's tasks")
        for record in recs:
            task = record["campaign"]["task_id"]
            manifest.require(task, pilot.rule_hash(record))
            assert record["period"]["id"] == period.id, task
            fit = record["fitness_config"]
            assert (fit["execution_lag"], fit["cost_multiplier"]) == (
                cfg.execution_lag,
                cfg.cost_multiplier,
            ), task
            arm = task.split("/")[0].removeprefix("arm")
            for name, series in pilot.evaluate_on_test(
                record, _subset(box, record["instruments"]), cfg, frozen
            ).items():
                runs[arm][name].append(series)
        for name, series in pilot.buy_and_hold(box, cfg).items():
            runs["BH"][name].append(series)
        yearly[period.id] = {arm: pilot.portfolio(by_inst) for arm, by_inst in runs.items()}
        access[period.id] = [{k: str(v) for k, v in asdict(r).items()} for r in box.access_log]
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
    result["read_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    result["test_access"] = access
    out_json.write_text(json.dumps(result, indent=1, default=float))
    lines = [
        "# WP2 pilot go/no-go (protocol §8)",
        "",
        f"Freeze manifest committed in {manifest.commit[:12]}; test years 2006-07..2008-06 read "
        f"once; {len(PILOT_INSTRUMENTS)} instruments; equal-weight portfolios of all runs.",
        "",
        f"**Decision: {result['decision']}** ({result['rule']}; difference "
        f"{result['difference']:+.3f}).",
        "",
        "| arm | pooled Sharpe | PL1 test | PL2 test |",
        "|---|---:|---:|---:|",
    ]
    for arm, value in sorted(result["pooled_sharpe"].items()):
        y = result["yearly_sharpe"]
        lines.append(f"| {arm} | {value:.3f} | {y['PL1'][arm]:.3f} | {y['PL2'][arm]:.3f} |")
    lines += ["", "| comparison | difference | 95% CI | p |", "|---|---:|---|---:|"]
    for name, c in result["comparisons"].items():
        lines.append(
            f"| {name} | {c['difference']:+.3f} | [{c['ci_low']:+.3f}, {c['ci_high']:+.3f}] | "
            f"{c['p_value']:.3f} |"
        )
    (REPORTS / "pilot_go_no_go.md").write_text("\n".join(lines) + "\n")
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
        "step",
        choices=("portability", "calibrate", "budget-check", "gonogo", "freeze", "pilot-test"),
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--mode", choices=("all", "plan", "report"), default="all")
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    if args.step == "portability":
        step_portability(paths, settings, args.workers, args.mode)
    elif args.step == "calibrate":
        step_calibrate(paths, settings, args.workers, args.mode)
    elif args.step == "budget-check":
        step_budget_check(paths, settings, args.workers, args.mode)
    elif args.step == "gonogo":
        step_gonogo(paths, settings, args.workers, args.mode)
    elif args.step == "freeze":
        step_freeze(paths, settings)
    else:
        step_pilot_test(paths, settings)


if __name__ == "__main__":
    main()
