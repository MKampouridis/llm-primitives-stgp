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
from lpstgp.campaign.plan import (
    PLAN_IDENTITY,
    Config,
    data_digest,
    settings_digest,
    source_digest,
    write_plan,
)
from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.data.store import modelling_store
from lpstgp.freeze import FreezeManifest, claim_test_read, digest, write_manifest
from lpstgp.operators.registry import LOCK_FILE as OPERATOR_LOCK
from lpstgp.runner import configs_from_settings
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, pilot_periods
from lpstgp.strategies import registry

CALIBRATION_INSTRUMENTS = ("SPX", "NKY", "EURUSD", "USDJPY", "GOLD", "NATGAS")  # protocol §6.1
PILOT_INSTRUMENTS = (
    "SPX", "NDX", "SMI", "DAX", "CAC", "UKX", "NKY", "HSI", "KOSPI", "AS51",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "NATGAS", "GOLD", "SILVER", "COPPER",
)  # fmt: skip
GP_ARMS = {"2a": "s2a", "2b": "s2b", "2c": "s2c", "6": "seed", "TA": "technical"}
CAL_BUDGET = 50_000
CAL_POPULATIONS, CAL_TOURNAMENTS = (250, 500, 1000), (3, 5)  # protocol §6.1
CAL_RUNS, BUDGET_RUNS, GONOGO_RUNS = 10, 3, 10  # per arm and instrument (§6.1, §6.2, §7)
UNIQUE_CEILING = 10  # unique budget: at most this many times the calibrated generations
REPORTS = REPO_ROOT / "reports" / "wp2"


def prepare(name, configs, cells, runs, paths, settings, workers: int, mode: str) -> Path | None:
    """Plan (unless reporting), run here (mode all) and return the plan once every task is done."""
    plan_path = paths.results_dir / "campaigns" / name / "tasks.json"
    if mode != "report":
        plan_path = write_plan(name, configs, cells, runs, paths, settings, register=register())
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


def register() -> Path:
    """The trial register (reports/configuration_register.csv) beside this step's reports."""
    return REPORTS.parent / "configuration_register.csv"


def revision() -> str:
    """The code revision of the repository the reports belong to (freeze and test read)."""
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
        check=True,
    )  # fmt: skip
    return out.stdout.strip()


def provenance(settings, plan_paths) -> dict:
    """What a calibration report was computed from: code, settings and its plans (D-051)."""
    return {
        "source_digest": source_digest(),
        "settings_digest": settings_digest(settings),
        "plans": {
            load_plan(p)["campaign"]: digest({k: load_plan(p)[k] for k in PLAN_IDENTITY})
            for p in plan_paths
        },
    }


def _current(report: dict, name: str) -> None:
    """Refuse a report computed from other code or settings than the current ones."""
    prov = report.get("provenance", {})
    now = {"source_digest": source_digest(), "settings_digest": settings_digest(load_settings())}
    stale = [k for k, v in now.items() if prov.get(k) != v]
    if stale:
        raise SystemExit(f"{name} is stale ({', '.join(stale)} changed); run that step again")


def chosen_parameters() -> dict:
    choice = json.loads((REPORTS / "calibration.json").read_text())
    _current(choice, "calibration.json")
    return choice


def step_calibrate(paths, settings, workers: int, mode: str = "all") -> None:
    configs = [
        Config(
            f"cal-{arm}-p{pop}-t{tour}",
            arm,
            gp={"population": pop, "generations": CAL_BUDGET // pop - 1, "tournament": tour},
        )
        for arm in ("s2c", "seed")
        for pop in CAL_POPULATIONS
        for tour in CAL_TOURNAMENTS
    ]
    cells = [((name,), "PL1") for name in CALIBRATION_INSTRUMENTS]
    plan = prepare("wp2-calibration", configs, cells, CAL_RUNS, paths, settings, workers, mode)
    if plan is None:
        return
    choice = calibration.choose_candidate(records(plan))
    REPORTS.mkdir(parents=True, exist_ok=True)
    choice["provenance"] = provenance(settings, [plan])
    (REPORTS / "calibration.json").write_text(json.dumps(choice, indent=1))
    lines = [
        "# WP2 calibration: GP parameters at equal budget (protocol §6.1)",
        "",
        f"Arms 2c and 6 pooled; {', '.join(CALIBRATION_INSTRUMENTS)}; PL1 training data only; "
        f"{CAL_RUNS} runs per arm and instrument; {CAL_BUDGET:,} requested evaluations per candidate.",
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


LAMBDA_STEPS = (1, 2, 4)  # protocol §6.3: lambda_turnover x1, then x2, then x4


def _lambda_stage(m, gp, cells, paths, settings, workers, mode) -> Path | None:
    """The budget-check runs at lambda_turnover x m; the plan once all its tasks are done."""
    name = "wp2-budget-check" if m == 1 else f"wp2-budget-check-lambda{m}"
    fitness = {} if m == 1 else {"lambda_turnover": m * settings["fitness"]["lambda_turnover"]}
    configs = [Config(f"bud-{arm}", lib, gp=gp, fitness=fitness) for arm, lib in GP_ARMS.items()]
    if mode == "all":
        return prepare(name, configs, cells, BUDGET_RUNS, paths, settings, workers, "all")
    plan_path = paths.results_dir / "campaigns" / name / "tasks.json"
    if mode == "plan" or not plan_path.exists():
        prepare(name, configs, cells, BUDGET_RUNS, paths, settings, workers, "plan")
    status = progress(plan_path, settings)
    if status["complete"] != status["tasks"]:
        print(f"{name}: {status['complete']} of {status['tasks']} tasks complete; run them, "
              "then `budget-check --mode report` again")  # fmt: skip
        return None
    return plan_path


def step_budget_check(paths, settings, workers: int, mode: str = "all") -> None:
    c = chosen_parameters()
    gp = {
        "population": c["population"],
        "generations": c["generations"],
        "tournament": c["tournament"],
    }
    cells = [((name,), "PL1") for name in CALIBRATION_INSTRUMENTS]
    out_json = REPORTS / "budget_check.json"
    # A check under way invalidates any earlier decision until it finishes (D-051).
    out_json.write_text(json.dumps({"status": "pending", "lambda_turnover_multiplier": None}))
    plan = _lambda_stage(1, gp, cells, paths, settings, workers, mode)
    if plan is None:
        return
    stages = {1: plan}
    base_recs = records(plan)
    lam = calibration.lambda_check(base_recs)  # every multiplier judged on step-2 runs (D-051)
    trials = [{"multiplier": 1, **lam}]
    chosen = 1 if not (lam["raise_lambda_turnover"] or lam["no_trade_exceeded"]) else None
    if lam["raise_lambda_turnover"] and not lam["no_trade_exceeded"]:
        for m in LAMBDA_STEPS[1:]:  # raise stepwise until both conditions hold
            stage = _lambda_stage(m, gp, cells, paths, settings, workers, mode)
            if stage is None:
                return
            stages[m] = stage
            check = calibration.lambda_check(records(stage))
            trials.append({"multiplier": m, **check})
            if check["no_trade_exceeded"]:  # a higher lambda can only make rules quieter
                break
            if not check["raise_lambda_turnover"]:
                chosen = m
                break
    recs = records(stages[chosen]) if chosen else base_recs  # the runs the go/no-go will match
    step1 = records(paths.results_dir / "campaigns" / "wp2-calibration" / "tasks.json")
    out = {
        "status": "resolved" if chosen else "unresolved",
        "budget_unit": calibration.budget_unit(recs),
        "lambda": lam,
        "lambda_trials": trials,
        "lambda_step1_descriptive": calibration.lambda_check(step1),
        # None: unresolved (no-trade limit exceeded, or x4 not enough): needs a recorded decision
        "lambda_turnover_multiplier": chosen,
        # The chosen values live here and in calibration.json, never in settings.toml (D-050):
        # the go/no-go refuses if the settings' base lambda is no longer this one.
        "base_lambda_turnover": settings["fitness"]["lambda_turnover"],
        "calibration_digest": digest(c),
        "provenance": provenance(settings, list(stages.values())),
    }
    out_json.write_text(json.dumps(out, indent=1))
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
    lines += [
        "",
        f"Spread of unique shares: {out['budget_unit']['spread']:.2f}x -> budget unit "
        f"**{out['budget_unit']['unit']}** (rule: unique if > 2x).",
        "",
        "| lambda_turnover | runs | final rules with no trade | median validation turnover |",
        "|---:|---|---:|---:|",
    ]
    for t in trials:
        runs = "step 2" if t["multiplier"] == 1 else "step 2 again"
        lines.append(
            f"| x{t['multiplier']} | {runs} | {t['no_trade_share']:.1%} | "
            f"{t['median_turnover']:.1f} |"
        )
    verdict = (
        f"**lambda_turnover x{chosen}**"
        if chosen
        else "**unresolved**: a recorded decision is needed before the go/no-go (D-047)"
    )
    d1 = out["lambda_step1_descriptive"]
    lines += [
        "",
        f"Rule: no-trade share <= 25% and median turnover <= 50 a year -> {verdict}.",
        f"For reference, the step-1 runs (all candidates, arms 2c and 6): no trade "
        f"{d1['no_trade_share']:.1%}, median turnover {d1['median_turnover']:.1f} (D-051).",
    ]
    (REPORTS / "budget_check.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(out, indent=1))


def gonogo_configs() -> list[Config]:
    c = chosen_parameters()
    check = json.loads((REPORTS / "budget_check.json").read_text())
    if check.get("status") == "pending":
        raise SystemExit("budget_check.json: a budget check is under way; finish it first")
    _current(check, "budget_check.json")
    if check.get("calibration_digest") != digest(c):
        raise SystemExit("budget_check.json was computed from another calibration; rerun it")
    m = check.get("lambda_turnover_multiplier")
    override = REPORTS / "lambda_decision.json"
    if (
        m is None and check.get("status") == "unresolved" and override.exists()
    ):  # a recorded decision resolves §6.3 (D-050)
        decision = json.loads(override.read_text())
        m = decision["lambda_turnover_multiplier"]
        if not str(decision.get("decision", "")).startswith("D-"):
            raise SystemExit(f'{override}: name the decision ("decision": "D-0xx")')
    if m is None:  # §6.3 not resolved: never plan the go/no-go on unchecked fitness weights
        raise SystemExit(
            "budget_check.json: lambda_turnover unresolved; record a decision in "
            f"docs/decisions.md and in {override}"
        )
    base = load_settings()["fitness"]["lambda_turnover"]
    if base != check["base_lambda_turnover"]:  # e.g. the chosen value written into settings
        raise SystemExit(
            f"settings lambda_turnover is {base}, but the budget check ran from "
            f"{check['base_lambda_turnover']}: keep the base value in settings.toml (D-050)"
        )
    fitness = {} if m == 1 else {"lambda_turnover": m * base}
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
    return [Config("arm1", "strategies", kind="select", fitness=fitness)] + [
        Config(f"arm{arm}", lib, gp=gp, fitness=fitness) for arm, lib in GP_ARMS.items()
    ]


def gonogo_plans(paths) -> list[Path]:
    return [
        paths.results_dir / "campaigns" / f"wp2-gonogo-{p}" / "tasks.json" for p in ("PL1", "PL2")
    ]


def check_gonogo_plan(plan_path: Path, settings) -> None:
    """Refuse a go/no-go plan whose configurations are not the current calibration decision."""
    expected = {c.name: c.digest(settings) for c in gonogo_configs()}
    planned = {k: c["digest"] for k, c in load_plan(plan_path)["configs"].items()}
    if planned != expected:
        raise SystemExit(f"{plan_path}: its configurations differ from the current calibration")


def step_gonogo(paths, settings, workers: int, mode: str = "all") -> None:
    for period, plan_path in zip(("PL1", "PL2"), gonogo_plans(paths), strict=True):
        if mode != "report":  # an identical plan is reused; a different one with records refused
            cells = [((name,), period) for name in PILOT_INSTRUMENTS]
            write_plan(
                f"wp2-gonogo-{period}", gonogo_configs(), cells, GONOGO_RUNS, paths, settings,
                register=register(),
            )  # fmt: skip
        check_gonogo_plan(plan_path, settings)
        if mode == "all":
            print(period, execute_plan(plan_path, paths, settings, workers))
        if mode == "report":
            records(plan_path)  # digests current and every task complete, or it refuses
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
    """Files under src/, scripts/ or config/ changed since ``revision`` (untracked ones too)."""
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", revision, "--", "src", "scripts",
         "config"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=all", "--",
         "src", "scripts", "config"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    untracked = [line[3:] for line in status.stdout.splitlines() if line.startswith("??")]
    return sorted(set(out.stdout.split()) | set(untracked))


def step_freeze(paths, settings) -> None:
    if source_changed_since("HEAD"):
        raise SystemExit("commit the code first: the manifest records the code revision")
    rules, short = {}, defaultdict(list)
    for plan_path in gonogo_plans(paths):
        check_gonogo_plan(plan_path, settings)
        recs = records(plan_path)  # every task, complete and current
        for r in recs:  # runs the generation ceiling ended before their unique budget
            if r.get("budget", {}).get("unit") == "unique" and not r["budget"]["cap_reached"]:
                short[r["campaign"]["config"]].append(r["campaign"]["task_id"])
        rules |= pilot.manifest_rules(recs)
    # Kept and reported, never a reason to stop: the rule is fixed in advance (D-052), because a
    # decision taken here would come after the go/no-go records exist (D-047).
    (REPORTS / "unique_budget_shortfall.json").write_text(
        json.dumps({arm: sorted(ids) for arm, ids in sorted(short.items())}, indent=1)
    )
    context = frozen_context(paths, settings) | {"code_version": revision()}
    path = REPORTS / "freeze_manifest.json"
    write_manifest(path, rules, context)
    counts = ", ".join(f"{arm} {len(ids)}" for arm, ids in sorted(short.items())) or "none"
    print(f"{len(rules)} rules frozen in {path}; runs short of the unique budget: {counts}")
    print("commit the manifest (and unique_budget_shortfall.json) before `pilot-test`")


def _evaluate(box: Sandbox, recs, frozen, cfg) -> dict:
    """Every frozen rule and buy-and-hold on ``box``, as equal-weight portfolios per arm."""
    runs: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for record in recs:
        arm = record["campaign"]["task_id"].split("/")[0].removeprefix("arm")
        for name, series in pilot.evaluate_on_test(
            record, _subset(box, record["instruments"]), cfg, frozen
        ).items():
            runs[arm][name].append(series)
    for name, series in pilot.buy_and_hold(box, cfg).items():
        runs["BH"][name].append(series)
    return {arm: pilot.portfolio(by_inst) for arm, by_inst in runs.items()}


def rehearse(validated, store, frozen, cfg, settings) -> None:
    """Run the whole test evaluation on each pilot period's VALIDATE year first, and discard it.

    Any error of code, library or data (missing costs, non-finite returns, ...) then surfaces
    before the one test read is claimed, not half-way through it (D-050).
    """
    from dataclasses import replace

    lmax = settings["splits"]["lookback_max_bars"]
    yearly = {}
    for period in pilot_periods(settings):
        box = Sandbox.open(store, period, Stage.VALIDATE, PILOT_INSTRUMENTS, lmax)
        as_test = replace(box, period=replace(period, test_start=period.val_start))
        yearly[period.id] = _evaluate(as_test, validated[period.id], frozen, cfg)
    pooled = {
        arm: tuple(np.concatenate([yearly[p][arm][k] for p in yearly]) for k in (0, 1))
        for arm in yearly[pilot_periods(settings)[0].id]
    }
    pilot.go_no_go(pooled, yearly, resamples=100)
    print("rehearsal on the validation years: complete")


def step_pilot_test(paths, settings) -> None:
    out_json = REPORTS / "pilot_go_no_go.json"
    if out_json.exists():  # protocol §8: the test years are read once
        raise SystemExit(f"{out_json} exists: the pilot test years have already been read")
    manifest = FreezeManifest.load_committed(REPORTS / "freeze_manifest.json", repo=REPO_ROOT)
    frozen_code = manifest.context["code_version"]
    manifest.check_context(frozen_context(paths, settings) | {"code_version": frozen_code})
    if changed := source_changed_since(frozen_code):
        raise SystemExit(f"code changed since the freeze: {', '.join(changed)}")
    _, cfg = configs_from_settings(settings)
    frozen = registry.load_frozen()
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    # 1. Validate everything before any test bar is read: records, rule hashes, settings.
    validated: dict[str, list[dict]] = {}
    for period, plan_path in zip(pilot_periods(settings), gonogo_plans(paths), strict=True):
        recs = records(plan_path)
        expected = {t for t in manifest.rules if t.split("/")[1] == period.id}
        if {r["campaign"]["task_id"] for r in recs} != expected:
            raise SystemExit(f"{period.id}: the records do not match the manifest's tasks")
        for record in recs:
            task = record["campaign"]["task_id"]
            manifest.require(task, pilot.rule_hash(record))
            if record["period"]["id"] != period.id:
                raise SystemExit(f"{task}: record of period {record['period']['id']}")
            fit = record["fitness_config"]
            if (fit["execution_lag"], fit["cost_multiplier"]) != (
                cfg.execution_lag,
                cfg.cost_multiplier,
            ):
                raise SystemExit(f"{task}: execution lag or costs differ from the settings")
        validated[period.id] = recs
    # 2. Claim the one read before opening the test stage. The claim is created atomically and
    #    is never removed by this script: after a crash, a second read needs a recorded decision
    #    (protocol §8; D-049), and the claim file must then be removed by hand.
    rehearse(validated, store, frozen, cfg, settings)
    claim_test_read(REPORTS / "pilot_test_claim.json", manifest)
    # 3. The one read.
    yearly: dict[str, dict] = {}
    raw: dict[str, np.ndarray] = {}
    access: dict[str, list] = {}
    for period in pilot_periods(settings):
        box = Sandbox.open_pilot_test(
            store,
            period,
            PILOT_INSTRUMENTS,
            lmax,
            pilot_periods=pilot_periods(settings),
            manifest=manifest,
        )
        yearly[period.id] = _evaluate(box, validated[period.id], frozen, cfg)
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
    shortfall = REPORTS / "unique_budget_shortfall.json"
    if shortfall.exists():  # reported beside the decision (D-052)
        result["unique_budget_shortfall"] = {
            arm: len(ids) for arm, ids in json.loads(shortfall.read_text()).items()
        }
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
