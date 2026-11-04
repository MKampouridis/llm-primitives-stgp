"""WP4 steps (docs/protocol_wp4.md). Every data read goes through the sandbox: FIT and VALIDATE
for every step but `test`, which opens the frozen test years once (D-086).

Steps:
  eligibility  the eligible instruments of P01..P18 and PC (counts only; D-083), committed as
               reports/wp4/eligibility.json for the maintenance and reported-run campaigns.
  plan         M4: one campaign plan per period (wp4-<period>) with every arm at 50 runs (D-082);
               the maintained arms take their period's final library and seeds from the M3
               campaign (--maintenance wp4). Plans go to CERES (scripts/ceres/tasks.sge).
  freeze       M5: every reported rule of P01..P18, per-period rule lists under results and
               their digests in reports/wp4/freeze_manifest.json (commit it).
  test         M6: --decision D-0xx (the PI's recorded go-ahead). Rehearsal on the validation
               years, then the single read of the test years; reports/wp4/primary.json.
  runs-study   M2: protocol.md §6.4, 100 runs of arm 2c on the 6 calibration instruments,
               PL1 and PL2 training data; decides 30 or 50 runs per configuration.

--mode: `plan` writes the campaign plan for CERES (scripts/ceres/tasks.sge); `report` reads the
finished records and writes reports/wp4/runs_study.{json,md}; `all` plans, runs here and reports.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp2_pilot  # the plan helpers and the calibration instruments
from lpstgp import runs_study
from lpstgp.campaign.plan import Config, write_plan
from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.data import eligibility

REPORTS = REPO_ROOT / "reports" / "wp4"
RUNS_STUDY = "wp4-runs-study"


def gp_arm(name: str, library: str, settings) -> Config:
    """A GP arm at WP2's calibrated parameters and fitness (D-054, D-056), read from the
    committed WP2 reports. WP2's own staleness check does not apply: those reports are final."""
    choice = json.loads((wp2_pilot.REPORTS / "calibration.json").read_text())
    check = json.loads((wp2_pilot.REPORTS / "budget_check.json").read_text())
    if check["budget_unit"]["unit"] != "requested" or check["lambda_turnover_multiplier"] != 1:
        raise SystemExit("budget_check.json is not the D-056 result (requested evaluations, λ ×1)")
    gp = {k: choice[k] for k in ("population", "generations", "tournament")}
    return Config(name, library, gp=gp)


def runs_study_config(settings) -> Config:
    """Arm 2c exactly as in the go/no-go, renamed: its digest must equal the registered one."""
    config = gp_arm("runs-2c", "s2c", settings)
    registered = {
        row.split(",")[2]: row.split(",")[5]
        for row in wp2_pilot.register().read_text().splitlines()
        if row.split(",")[1:2] == ["wp2-gonogo-PL1"]
    }
    if config.digest(settings) != registered["arm2c"]:
        raise SystemExit("runs-2c differs from the go/no-go's arm 2c (settings or locks changed)")
    return config


def step_runs_study(paths, settings, workers: int, mode: str) -> None:
    cells = [((inst,), p) for p in ("PL1", "PL2") for inst in wp2_pilot.CALIBRATION_INSTRUMENTS]
    plan = wp2_pilot.prepare(
        RUNS_STUDY,
        [runs_study_config(settings)],
        cells,
        runs_study.RUNS,
        paths,
        settings,
        workers,
        mode,
    )
    if plan is None:
        return
    result = runs_study.decide(runs_study.cells(wp2_pilot.records(plan)))
    result |= {"provenance": wp2_pilot.provenance(settings, [plan])}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "runs_study.json").write_text(json.dumps(result, indent=1, default=str) + "\n")
    lines = [
        "# WP4 runs-per-configuration study (protocol.md §6.4)",
        "",
        f"Arm 2c, {runs_study.RUNS} runs on each of {result['cells']} (instrument, period) cells "
        "(PL1 and PL2 training data; validation Sharpe of each run's selected rule).",
        "",
        f"- 95th percentile of |median of {runs_study.SUBSET} − median of {runs_study.RUNS}|: "
        f"**{result['p95_deviation']:.4f}** (tolerance {runs_study.TOLERANCE}).",
        f"- **Runs per configuration in WP4: {result['runs_per_configuration']}.**",
        "",
        "| cell | 95th percentile | median |",
        "|---|---:|---:|",
    ]
    lines += [
        f"| {k} | {v['p95_deviation']:.4f} | {v['median_deviation']:.4f} |"
        for k, v in result["per_cell"].items()
    ]
    (REPORTS / "runs_study.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:6]))


RUNS = 50  # per configuration (D-082)
FIXED_ARMS = {  # arm -> library (protocol_wp4 §3)
    "arm2a": "s2a", "arm2b": "s2b", "arm2c": "s2c", "arm3": "arm3", "arm6": "seed",
    "armGPconv": "conventional", "armTA": "technical",
}  # fmt: skip
MAINTAINED = {"arm4grow": "4-grow", "arm4full": "4-full", "arm5": "5"}


_SPECS: dict[str, dict] = {}


def expected_maintenance_spec(campaign: str) -> dict:
    """The specification M3 runs under (``scripts/maintain.py --wp4``): P01..P18 then PC, each
    period on its eligible instruments, the WP3 protocol's runs, cycles and GP budget, and the
    current settings, data and source digests. Built without writing anything."""
    if campaign not in _SPECS:
        from lpstgp.maintenance import cycle

        table = json.loads((REPORTS / "eligibility.json").read_text())["eligible"]
        loop = cycle.Cycle(campaign, list(table), instruments=table, check=False)
        _SPECS[campaign] = json.loads(json.dumps(loop.spec, default=str))
    return _SPECS[campaign]


def maintained_state(paths, campaign: str, arm: str, period: str) -> dict:
    """The library state and seed rules after a period's last maintenance cycle, L(p, C): from a
    cycle record made under the campaign's own specification, and the same as the last row of
    the period's lineage, whose hash the freeze records (D-087)."""
    from lpstgp.freeze import digest
    from lpstgp.maintenance.cycle import CYCLES, ArmState

    root = paths.results_dir / "wp3" / "maintenance" / campaign
    record = json.loads((root / arm / period / f"c{CYCLES}" / "cycle.json").read_text())
    spec = json.loads((root / "campaign.json").read_text())
    if spec != expected_maintenance_spec(campaign):
        raise SystemExit(
            f"maintenance {campaign}: its specification is not WP4's M3 design under the current "
            "code, settings and data (D-088)"
        )
    if record.get("spec_digest") != digest(spec):
        raise SystemExit(f"{arm} {period}: the last cycle was made under another specification")
    lineage = json.loads((root / arm / period / "lineage.json").read_text())
    last = lineage["cycles"][-1]
    out = record["state_out"]
    if (last["cycle"], last["state_out"], last["rules_out"]) != (
        CYCLES,
        out["state_id"],
        ArmState.from_dict(out).batch_key,
    ):
        raise SystemExit(f"{arm} {period}: the lineage does not end on the last cycle's state")
    return out


def wp4_configs(paths, settings, period: str, maintenance: str | None) -> list[Config]:
    """Every arm of protocol_wp4 §3 for one period, at WP2's calibrated parameters."""
    configs = [Config("arm1", "strategies", kind="select")]
    configs += [gp_arm(name, lib, settings) for name, lib in FIXED_ARMS.items()]
    if maintenance is None:
        return configs
    for name, arm in MAINTAINED.items():
        out = maintained_state(paths, maintenance, arm, period)
        base = gp_arm(name, f"state:{out['state_id']}", settings)
        rules = tuple(tuple(r) for r in out.get("seed_rules", ()))
        if arm == "5":  # arm 5 keeps arm 3's library; its seeds vary (WP3 protocol §4.2)
            base = gp_arm(name, "arm3", settings)
        configs.append(Config(base.name, base.library, gp=base.gp, seed_rules=rules))
    return configs


def design_cells(period: str) -> list[tuple[tuple[str, ...], str]]:
    table = json.loads((REPORTS / "eligibility.json").read_text())["eligible"]
    return [((inst,), period) for inst in table[period]]


def design_tasks(paths, settings, period: str, maintenance: str | None) -> list[dict]:
    """The tasks protocol_wp4 §4 prescribes for a period, as a plan stores them."""
    from lpstgp.campaign.plan import plan_tasks

    configs = wp4_configs(paths, settings, period, maintenance)
    return json.loads(json.dumps(plan_tasks(configs, design_cells(period), RUNS)))


def step_plan(paths, settings, periods, maintenance: str | None) -> None:
    for period in periods:
        configs = wp4_configs(paths, settings, period, maintenance)
        cells = design_cells(period)
        name = f"wp4-{period}" if maintenance else f"wp4-{period}-fixed"
        plan = write_plan(
            name, configs, cells, RUNS, paths, settings, register=wp2_pilot.register(),
            record_format="json.gz",  # about 3 GB for all of WP4 instead of about 20 (D-085)
        )  # fmt: skip
        print(f"{name}: {len(json.loads(plan.read_text())['tasks'])} tasks")


FREEZE_DIR = "wp4/freeze"  # under results: the per-period rule lists, whose digests are committed


def plan_path(paths, period: str) -> Path:
    return paths.results_dir / "campaigns" / f"wp4-{period}" / "tasks.json"


def frozen_context(paths, settings, periods, maintenance: str) -> dict:
    """What the frozen rules' test evaluation depends on besides the rules (D-079, D-086)."""
    from lpstgp.campaign.execute import load_plan
    from lpstgp.campaign.plan import AUTHORED_LOCK, settings_digest, tier_digest
    from lpstgp.operators.registry import LOCK_FILE as OPERATOR_LOCK
    from lpstgp.strategies import registry

    context = {
        "test_periods": sorted(periods),
        "settings_digest": settings_digest(settings),
        "strategies_lock": registry.lock_digest(),
        "operator_lock": registry.file_hash(OPERATOR_LOCK),
        "authored_lock": registry.file_hash(AUTHORED_LOCK),
        "tier_digest": tier_digest(paths),
    }
    for period in periods:
        plan = load_plan(plan_path(paths, period))
        # every configuration as M3 left it: a plan built from another maintenance run, or
        # before M3 finished, is refused here (D-087)
        expected = {
            c.name: c.digest(settings) for c in wp4_configs(paths, settings, period, maintenance)
        }
        if expected != {k: c["digest"] for k, c in plan["configs"].items()}:
            raise SystemExit(
                f"{period}: the plan's configurations differ from maintenance {maintenance}"
            )
        # and every task of the design: each eligible instrument, every run, its paired seed
        if plan["tasks"] != design_tasks(paths, settings, period, maintenance):
            raise SystemExit(f"{period}: the plan's tasks are not WP4's design (D-088)")
        context[f"plan:{plan['campaign']}"] = {
            "settings_digest": plan["settings_digest"],
            "source_digest": plan["source_digest"],
            "configs": {k: c["digest"] for k, c in sorted(plan["configs"].items())},
            "tasks": len(plan["tasks"]),
        }
    root = paths.results_dir / "wp3" / "maintenance" / maintenance
    spec = root / "campaign.json"
    context["maintenance"] = {
        "campaign": maintenance,
        "specification": registry.file_hash(spec) if spec.exists() else None,
        "lineage": {
            str(p.relative_to(root)): registry.file_hash(p)
            for p in sorted(root.glob("*/*/lineage.json"))
        },
    }
    return context


def step_freeze(paths, settings, periods, maintenance: str) -> None:
    """M5: every reported rule of P01..P18 frozen; the committed manifest holds one digest per
    period's rule list (about 250,000 rules would not fit in git; D-086)."""
    from lpstgp import pilot
    from lpstgp.campaign.execute import iter_plan_records
    from lpstgp.freeze import digest, write_manifest

    if changed := wp2_pilot.source_changed_since("HEAD"):
        raise SystemExit(
            "commit the code first: the manifest records the code revision "
            f"({', '.join(changed[:5])}{' ...' if len(changed) > 5 else ''})"
        )
    out_dir = paths.results_dir / FREEZE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    digests = {}
    for period in periods:
        records = iter_plan_records(plan_path(paths, period), paths, settings, keep=pilot.slim)
        rules = pilot.manifest_rules(list(records))
        text = json.dumps(rules, sort_keys=True, separators=(",", ":"))
        (out_dir / f"{period}.json").write_text(text)
        digests[period] = {"rules": len(rules), "sha256": digest(rules)}
        print(f"{period}: {len(rules)} rules frozen")
    context = frozen_context(paths, settings, periods, maintenance)
    context["code_version"] = wp2_pilot.revision()
    write_manifest(REPORTS / "freeze_manifest.json", digests, context)
    print("commit reports/wp4/freeze_manifest.json before `test`")


def period_rules(paths, manifest, period: str) -> dict[str, str]:
    """A period's frozen rule list, checked against its committed digest."""
    from lpstgp.freeze import digest

    rules = json.loads((paths.results_dir / FREEZE_DIR / f"{period}.json").read_text())
    expected = manifest.rules[period]
    if digest(rules) != expected["sha256"] or len(rules) != expected["rules"]:
        raise SystemExit(f"{period}: the frozen rule list differs from the committed manifest")
    return rules


def _git_out(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)


CLAIM = "reports/wp4/test_claim.json"


def recorded_go_ahead(decision: str, manifest_commit: str) -> None:
    """The test read needs the PI's go-ahead, recorded first (CLAUDE.md rule 1): a decision
    titled with it, committed after the freeze manifest (D-087)."""
    shown = _git_out("show", "HEAD:docs/decisions.md")
    lines = shown.stdout.splitlines() if shown.returncode == 0 else []
    heading = [line for line in lines if line.startswith(f"### {decision} ")]
    if not heading or "test read" not in heading[0].lower() or "PI" not in heading[0]:
        raise SystemExit(f"{decision}: no committed decision titled with the PI's WP4 test read")
    added = _git_out(
        "log", "--format=%H", "--reverse", "-S", heading[0], "--", "docs/decisions.md"
    ).stdout.split()
    if (
        not added
        or added[0] == manifest_commit
        or _git_out("merge-base", "--is-ancestor", manifest_commit, added[0]).returncode != 0
    ):
        raise SystemExit(f"{decision}: the go-ahead must be committed after the freeze manifest")


def never_claimed() -> None:
    """A claim committed on either Mac (D-055) refuses the read for good, even if the file is
    gone from this working tree."""
    if (REPO_ROOT / CLAIM).exists() or _git_out(
        "log", "--all", "--format=%H", "--", CLAIM
    ).stdout.strip():
        raise SystemExit(f"{CLAIM} exists or was committed: the WP4 test years have been claimed")


def step_test(paths, settings, periods, maintenance: str, decision: str) -> None:
    """M6: rehearsal on the validation years, then the single read of P01..P18's test years."""
    from lpstgp import pilot, wp4_test
    from lpstgp.analysis import wp4 as analysis
    from lpstgp.campaign.execute import iter_plan_records
    from lpstgp.data.store import modelling_store
    from lpstgp.freeze import FreezeManifest, claim_test_read
    from lpstgp.runner import configs_from_settings
    from lpstgp.sandbox import Sandbox
    from lpstgp.splits import Stage, all_periods
    from lpstgp.strategies import registry

    out_json = REPORTS / "primary.json"
    if out_json.exists():
        raise SystemExit(f"{out_json} exists: the WP4 test years have already been read")
    manifest = FreezeManifest.load_committed(REPORTS / "freeze_manifest.json", repo=REPO_ROOT)
    recorded_go_ahead(decision, manifest.commit)
    never_claimed()
    frozen_code = manifest.context["code_version"]
    current = frozen_context(paths, settings, periods, maintenance)
    manifest.check_context(current | {"code_version": frozen_code})
    if changed := wp2_pilot.source_changed_since(frozen_code):
        raise SystemExit(f"code changed since the freeze: {', '.join(changed)}")
    _, cfg = configs_from_settings(settings)
    frozen = registry.load_frozen()
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    by_id = all_periods(settings)
    test_periods = tuple(by_id[p] for p in periods)
    table = json.loads((REPORTS / "eligibility.json").read_text())["eligible"]
    # 1. Every record checked against the frozen lists before any test bar is read.
    validated = {}
    for period in periods:
        rules = period_rules(paths, manifest, period)
        # slim records: the rule and metadata only, about 1 KB instead of about 180 KB (D-088)
        recs = list(iter_plan_records(plan_path(paths, period), paths, settings, keep=pilot.slim))
        if {r["campaign"]["task_id"] for r in recs} != set(rules):
            raise SystemExit(f"{period}: the records do not match the frozen tasks")
        for r in recs:
            if pilot.rule_hash(r) != rules[r["campaign"]["task_id"]]:
                raise SystemExit(f"{r['campaign']['task_id']}: rule differs from the frozen one")
        validated[period] = recs
    # 2. Rehearsal: the whole evaluation on the validation years (VALIDATE data), kept as the
    #    validation side of H3's gap; any code or data error surfaces before the claim.
    validation = {}
    for period in periods:
        box = Sandbox.open(store, by_id[period], Stage.VALIDATE, table[period], lmax)
        series = wp4_test.evaluate_period(wp4_test.as_test(box), validated[period], cfg, frozen)
        wp4_test.check_replay(series)  # the saved arrays carry every secondary analysis (D-087)
        wp4_test.save(paths.results_dir / "wp4" / "validation" / f"{period}.npz", series)
        validation[period] = wp4_test.portfolios(series)
    arms = sorted(validation[periods[0]])
    analysis.primary(
        {a: analysis.concatenate({p: validation[p][a] for p in periods}, periods) for a in arms},
        resamples=50,
    )
    print("rehearsal on the validation years: complete")
    # 3. The claim, then the one read.
    claim_test_read(REPO_ROOT / CLAIM, manifest)
    print(f"claimed: commit {CLAIM} now, on this Mac, before anything else (D-087)")
    test, access = {}, {}
    for period in periods:
        box = Sandbox.open_frozen_test(
            store, by_id[period], table[period], lmax, test_periods=test_periods,
            manifest=manifest,
        )  # fmt: skip
        series = wp4_test.evaluate_period(box, validated[period], cfg, frozen)
        wp4_test.save(paths.results_dir / "wp4" / "test" / f"{period}.npz", series)
        wp4_test.check_replay(series)
        test[period] = wp4_test.portfolios(series)
        access[period] = [{k: str(v) for k, v in asdict(r).items()} for r in box.access_log]
    concatenated = {
        a: analysis.concatenate({p: test[p][a] for p in periods}, periods) for a in arms
    }
    result = analysis.primary(concatenated)
    result |= {
        "manifest_commit": manifest.commit,
        "decision": decision,
        "per_period_sharpe": {
            p: {a: analysis.portfolio_sharpe(test[p][a]) for a in arms} for p in periods
        },
        "per_period_validation_sharpe": {
            p: {a: analysis.portfolio_sharpe(validation[p][a]) for a in arms} for p in periods
        },
        "read_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "test_access": access,
    }
    out_json.write_text(json.dumps(result, indent=1, default=float))
    print(json.dumps({k: result[k] for k in ("sharpe", "comparisons")}, indent=1, default=float))


def step_eligibility(paths, settings) -> None:
    table = eligibility.table(paths, settings)
    pairs = sum(len(table[p]) for p in eligibility.WP4_PERIODS if p != "PC")
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = {
        "rule": "D-009 (504 warm-up bars, >= 95% session coverage); PC without its test year (D-083)",
        "primary_pairs": pairs,
        "eligible": table,
        "provenance": wp2_pilot.provenance(settings, []),
    }
    (REPORTS / "eligibility.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print({p: len(v) for p, v in table.items()}, "pairs P01-P18:", pairs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("step", choices=("eligibility", "plan", "freeze", "test", "runs-study"))
    parser.add_argument("--decision", help="test: the decision recording the PI's go-ahead")
    parser.add_argument("--periods", default=",".join(eligibility.WP4_PERIODS))
    parser.add_argument(
        "--maintenance", default="wp4", help="M3 campaign; 'none' plans the fixed arms only"
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--mode", choices=("all", "plan", "report"), default="plan")
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    if args.step == "eligibility":
        step_eligibility(paths, settings)
    elif args.step in ("freeze", "test"):
        primary = [p for p in args.periods.split(",") if p != "PC"]  # PC is frozen on its own
        if sorted(primary) != sorted(p for p in eligibility.WP4_PERIODS if p != "PC"):
            raise SystemExit("freeze and test cover exactly P01-P18 (protocol_wp4 §6; D-087)")
        if args.step == "freeze":
            step_freeze(paths, settings, primary, args.maintenance)
        else:
            step_test(paths, settings, primary, args.maintenance, args.decision or "")
    elif args.step == "plan":
        maintenance = None if args.maintenance == "none" else args.maintenance
        step_plan(paths, settings, args.periods.split(","), maintenance)
    else:
        step_runs_study(paths, settings, args.workers, args.mode)


if __name__ == "__main__":
    main()
