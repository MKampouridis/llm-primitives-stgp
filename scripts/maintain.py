"""WP3 maintenance cycles (arms 4-grow, 4-full, 5), resumable (docs/protocol_wp3.md §4).

Usage:
  uv run python scripts/maintain.py --stub                    # mechanics test, no LLM, tiny GP
  uv run python scripts/maintain.py --preflight               # isolation of a maintainer session
  uv run python scripts/maintain.py --campaign dryrun [--arms 4-grow,4-full,5] [--workers 6]

The dry run (M4) uses PL1 then PL2 training data, three cycles each. A finished cycle is skipped
on a re-run; an interrupted one resumes (its runs and its session).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from string import Template

from lpstgp.config import REPO_ROOT, load_paths
from lpstgp.maintenance import cycle, session, state, stub

TOY = REPO_ROOT / "tests" / "authoring" / "fixtures" / "toy_operator.py"


def claude_version() -> str:
    return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()


def run_stub(workers: int) -> None:
    """Every arm through two tiny periods with the scripted session (no LLM)."""
    paths = load_paths()
    root = paths.results_dir / "wp3" / "maintenance" / "stub"
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(paths.results_dir / "tierA" / "wp3-maintenance-stub", ignore_errors=True)
    loop = cycle.Cycle(
        "stub", ("PL1", "PL2"), instruments=("SPX", "EURUSD", "GOLD"), runs=1, cycles=2,
        workers=workers, gp_overrides={"population": 40, "generations": 3},
        session_runner=stub.run,
    )  # fmt: skip
    for arm in cycle.ARMS:
        for c in loop.run_arm(arm):
            d = c["decision"]
            print(
                f"{arm:7s} {c['period']} c{c['cycle']}: {d['status']:9s} {d.get('what', '')} "
                f"{c['state_in']['state_id']} -> {c['state_out']['state_id']} "
                f"gate={c['gate'] and round(c['gate']['median_difference'], 3)} "
                f"p_harm={c['gate'] and round(c['gate'].get('p_harm', float('nan')), 3)}"
            )


def run_preflight() -> None:
    from generate_strategies import summarise_stream

    paths = load_paths()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for arm in ("4-full", "5"):
        archive = paths.results_dir / "wp3" / "preflight_maintenance" / stamp / arm
        archive.mkdir(parents=True)
        arm3 = state.arm3_state()
        state.save(arm3, {}, paths.results_dir)
        context = {
            "arm": arm, "state_id": arm3.id, "library": state.PREFIX + arm3.id,
            "results_dir": str(paths.results_dir), "initial": {}, "initial_sha": {},
            "evidence": {}, "previous_evidence": None,
        }  # fmt: skip
        (archive / "context.json").write_text(json.dumps(context))
        brief = Template((session.PROMPTS / "preflight.md").read_text()).substitute(
            repo_readme=REPO_ROOT / "README.md", home=Path.home(), arm=arm,
            steps=PREFLIGHT_STEPS[arm],
        )  # fmt: skip
        session_id = str(uuid.uuid4())
        folder = session.GEN_ROOT / session_id
        session.prepare(folder, brief)
        if arm == "5":
            (folder / "rules.json").write_text('[{"entry": "Nope_v1(Ret_v1)", "exit": "x"}]')
        else:
            shutil.copyfile(TOY, folder / "toy_operator.py")
        cmd = session.claude_command(arm, folder, archive, session_id)
        cmd[cmd.index("--effort") + 1] = "low"
        result = session.wp2.run_claude(cmd, folder, archive, "stream", timeout=1800)
        session.wp2.copy_transcript(folder, session_id, archive)
        calls = summarise_stream(archive / "stream.jsonl")
        summary = {
            "claude_version": claude_version(),
            "command": cmd,
            **result,
            "tool_calls": calls,
        }
        (archive / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
        print(f"===== {arm}: models {summary.get('models')}, exit {summary.get('exit')}")
        for call in calls:
            print(
                f"{call['tool']:28s} error={call.get('is_error')!s:5s} -> {call.get('result', '')[:90]}"
            )
        print("final answer:\n" + str(result.get("result", "")))


PREFLIGHT_STEPS = {
    "4-full": (
        "7. Call the `check` tool on `toy_operator.py` (it is in your folder).\n"
        "8. Call the `describe` tool on `toy_operator.py`.\n"
        "9. Call the `check_patch` tool."
    ),
    "5": "7. Call the `check_rules` tool (it reads `rules.json` in your folder).",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--stub", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--campaign", default="dryrun")
    parser.add_argument("--periods", default="PL1,PL2")
    parser.add_argument("--arms", default=",".join(cycle.ARMS))
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.stub:
        run_stub(args.workers)
        return
    if args.preflight:
        run_preflight()
        return
    loop = cycle.Cycle(
        args.campaign, args.periods.split(","), workers=args.workers,
        claude_version=claude_version(),
    )  # fmt: skip
    for arm in args.arms.split(","):
        for c in loop.run_arm(arm):
            print(f"{arm} {c['period']} c{c['cycle']}: {c['decision']}")


if __name__ == "__main__":
    main()
