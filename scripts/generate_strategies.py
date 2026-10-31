"""WP2 strategy generation: isolated headless Claude Code sessions (D-035), resumable.

Usage:
  uv run python scripts/generate_strategies.py --preflight          # isolation test (archived)
  uv run python scripts/generate_strategies.py --dry-run            # render briefs and commands
  uv run python scripts/generate_strategies.py [--domains a,b] [--slots 1,2] [--parallel 2]

Sessions within a domain run in order (each later brief lists the earlier accepted strategies);
domains run in parallel. A slot whose summary is accepted is skipped on a re-run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from string import Template

from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.runner import configs_from_settings
from lpstgp.splits import Stage
from lpstgp.strategies import devtool, generation
from lpstgp.strategies.generation import DOMAINS, GEN_ROOT, Slot

TOY = REPO_ROOT / "tests" / "strategies" / "fixtures" / "toy_trend.py"


def claude_version() -> str:
    return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()


def archive_root(paths) -> Path:
    return paths.results_dir / "wp2" / "strategy_generation"


def summarise_stream(stream: Path) -> list[dict]:
    """Tool calls in a stream-json transcript and whether each succeeded."""
    calls, results = {}, {}
    for line in stream.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        message = event.get("message")
        content = message.get("content", []) if isinstance(message, dict) else []
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use":
                calls[block["id"]] = {
                    "tool": block["name"],
                    "input": json.dumps(block["input"])[:120],
                }
            elif block.get("type") == "tool_result":
                text = block.get("content")
                text = text if isinstance(text, str) else json.dumps(text)
                results[block["tool_use_id"]] = {
                    "is_error": block.get("is_error", False),
                    "result": text[:160],
                }
    return [{**call, **results.get(i, {})} for i, call in calls.items()]


def preflight(paths, settings) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = paths.results_dir / "wp2" / "preflight" / stamp
    archive.mkdir(parents=True)
    brief = Template((generation.PROMPTS / "preflight.md").read_text()).substitute(
        repo_readme=REPO_ROOT / "README.md", home=Path.home()
    )
    session_id = str(uuid.uuid4())
    folder = GEN_ROOT / session_id
    generation.prepare_session(folder, brief)
    shutil.copyfile(TOY, folder / "strategy.py")
    cmd = generation.claude_command(folder, archive, session_id)
    cmd[cmd.index("--effort") + 1] = "low"
    result = generation.run_claude(cmd, folder, archive, "stream", timeout=1800)
    generation.copy_transcript(folder, session_id, archive)
    calls = summarise_stream(archive / "stream.jsonl")
    summary = {"claude_version": claude_version(), "command": cmd, **result, "tool_calls": calls}
    (archive / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(
        json.dumps(
            {k: summary[k] for k in ("claude_version", "models", "exit", "num_turns")}, indent=1
        )
    )
    for call in calls:
        print(
            f"{call['tool']:28s} error={call.get('is_error')!s:5s} {call['input'][:60]} -> {call.get('result', '')[:90]}"
        )
    print(
        "\nfinal answer:\n"
        + json.loads((archive / "stream.jsonl").read_text().splitlines()[-1]).get("result", "")
    )


def run_domain(domain: str, slots: list[int], paths, settings, version: str) -> list[dict]:
    root = archive_root(paths)
    earlier, records = [], []
    for k in range(1, generation.SLOTS_PER_DOMAIN + 1):
        slot = Slot(domain, k)
        summary_path = root / slot.name / "summary.json"
        done = json.loads(summary_path.read_text()) if summary_path.exists() else None
        if done is None and k in slots:
            done = generation.run_session(
                slot, earlier, GEN_ROOT, root, paths, settings, claude_version=version
            )
        if done and done.get("accepted"):
            meta = done["strategy"]
            earlier.append({"name": meta["name"], "hypothesis": meta["hypothesis"]})
            records.append(done)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--domains", default=",".join(DOMAINS))
    parser.add_argument("--slots", default="1,2,3,4")
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    if args.preflight:
        preflight(paths, settings)
        return
    domains, slots = args.domains.split(","), [int(s) for s in args.slots.split(",")]
    if args.dry_run:
        _, fitness = configs_from_settings(settings)
        dev = devtool.build(paths, settings, Stage.FIT, paths.cache_dir / "dryrun")
        for domain in domains:
            slot = Slot(domain, slots[0])
            brief = generation.render_brief(slot, [], vars(fitness), dev)
            print(f"===== {slot.name} (brief {generation.sha12(brief)})\n{brief}")
        print(
            " ".join(generation.claude_command(GEN_ROOT / "ID", paths.cache_dir / "dryrun", "ID"))
        )
        return
    version = claude_version()
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = [pool.submit(run_domain, d, slots, paths, settings, version) for d in domains]
        done = [r for f in futures for r in f.result()]
    print(f"{len(done)} accepted strategies")


if __name__ == "__main__":
    main()
