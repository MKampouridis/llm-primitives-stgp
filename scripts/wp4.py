"""WP4 steps (docs/protocol_wp4.md). Data reads go through the sandbox, FIT/VALIDATE only.

Steps:
  eligibility  the eligible instruments of P01..P18 and PC (counts only; D-083), committed as
               reports/wp4/eligibility.json for the maintenance and reported-run campaigns.
  plan         M4: one campaign plan per period (wp4-<period>) with every arm at 50 runs (D-082);
               the maintained arms take their period's final library and seeds from the M3
               campaign (--maintenance wp4). Plans go to CERES (scripts/ceres/tasks.sge).
  runs-study   M2: protocol.md §6.4, 100 runs of arm 2c on the 6 calibration instruments,
               PL1 and PL2 training data; decides 30 or 50 runs per configuration.

--mode: `plan` writes the campaign plan for CERES (scripts/ceres/tasks.sge); `report` reads the
finished records and writes reports/wp4/runs_study.{json,md}; `all` plans, runs here and reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp2_pilot  # the plan helpers and the calibration instruments
from lpstgp import runs_study
from lpstgp.campaign.plan import Config
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


def maintained_state(paths, campaign: str, arm: str, period: str) -> dict:
    """The library state and seed rules after a period's last maintenance cycle, L(p, C)."""
    from lpstgp.maintenance.cycle import CYCLES

    path = paths.results_dir / "wp3" / "maintenance" / campaign / arm / period / f"c{CYCLES}"
    record = json.loads((path / "cycle.json").read_text())
    return record["state_out"]


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


def step_plan(paths, settings, periods, maintenance: str | None) -> None:
    table = json.loads((REPORTS / "eligibility.json").read_text())["eligible"]
    for period in periods:
        configs = wp4_configs(paths, settings, period, maintenance)
        cells = [((inst,), period) for inst in table[period]]
        name = f"wp4-{period}" if maintenance else f"wp4-{period}-fixed"
        wp2_pilot.prepare(name, configs, cells, RUNS, paths, settings, 1, "plan")


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
    parser.add_argument("step", choices=("eligibility", "plan", "runs-study"))
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
    elif args.step == "plan":
        maintenance = None if args.maintenance == "none" else args.maintenance
        step_plan(paths, settings, args.periods.split(","), maintenance)
    else:
        step_runs_study(paths, settings, args.workers, args.mode)


if __name__ == "__main__":
    main()
