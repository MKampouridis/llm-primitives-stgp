"""WP3 arm 3: LLM authoring of the cross-domain operator library (D-062), resumable.

Usage:
  uv run python scripts/author_operators.py --preflight     # isolation test (archived)
  uv run python scripts/author_operators.py --dry-run       # render the first brief and command
  uv run python scripts/author_operators.py [--domains a,b]  # the authoring sessions

One session per domain, in domain order; each later brief lists the operators accepted so far.
A domain whose summary is accepted is skipped on a re-run; a domain that fails after its repair
turn is re-run once in a fresh session (protocol_wp3 §3).
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

from lpstgp.authoring import generation
from lpstgp.authoring.generation import DOMAINS, GEN_ROOT, Slot
from lpstgp.config import REPO_ROOT, load_paths, load_settings
from lpstgp.splits import Stage
from lpstgp.strategies import devtool

TOY = REPO_ROOT / "tests" / "authoring" / "fixtures" / "toy_operator.py"


def claude_version() -> str:
    return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()


def archive_root(paths) -> Path:
    return paths.results_dir / "wp3" / "arm3_authoring"


def accepted_so_far(root: Path) -> tuple[list[dict], dict, set[str]]:
    """Earlier accepted operators (for the brief), declared kinds and names in use."""
    earlier, kinds, taken = [], {}, set()
    for domain in DOMAINS:
        for attempt in (1, 2):
            path = root / Slot(domain, attempt).name / "summary.json"
            if not path.exists():
                continue
            done = json.loads(path.read_text())
            if done.get("accepted"):
                for row in done["operators"]:
                    op = row["operator"]
                    earlier.append(
                        {
                            "domain": DOMAINS[domain][0],
                            "signature": op["signature"],
                            "summary": op["summary"],
                        }
                    )
                    taken.add(op["name"])
                kinds.update(done.get("kinds", {}))
    return earlier, kinds, taken


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--domains", default=",".join(DOMAINS))
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    root = archive_root(paths)
    if args.preflight:
        run_preflight(paths)
        return
    if args.dry_run:
        dev = devtool.build(paths, settings, Stage.FIT, paths.cache_dir / "dryrun_wp3")
        earlier, kinds, _ = accepted_so_far(root)
        slot = Slot(args.domains.split(",")[0])
        brief = generation.render_brief(slot, earlier, kinds, dev)
        print(f"===== {slot.name} (brief {generation.wp2.sha12(brief)})\n{brief}")
        cmd = generation.claude_command(GEN_ROOT / "ID", paths.cache_dir / "dryrun_wp3", "ID")
        print(" ".join(cmd))
        return
    version = claude_version()
    for domain in args.domains.split(","):
        for attempt in (1, 2):
            slot = Slot(domain, attempt)
            summary = root / slot.name / "summary.json"
            done = json.loads(summary.read_text()) if summary.exists() else None
            if done is None:
                earlier, kinds, taken = accepted_so_far(root)
                done = generation.run_session(
                    slot, earlier, kinds, taken, GEN_ROOT, root, paths, settings,
                    claude_version=version,
                )  # fmt: skip
            print(f"{slot.name}: accepted={done.get('accepted')} {done.get('problems', '')}")
            if done.get("accepted"):
                break


def run_preflight(paths) -> None:
    from generate_strategies import summarise_stream

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = paths.results_dir / "wp3" / "preflight" / stamp
    archive.mkdir(parents=True)
    brief = Template((generation.PROMPTS / "preflight.md").read_text()).substitute(
        repo_readme=REPO_ROOT / "README.md", home=Path.home()
    )
    session_id = str(uuid.uuid4())
    folder = GEN_ROOT / session_id
    generation.prepare_session(folder, brief)
    shutil.copyfile(TOY, folder / "toy_operator.py")
    cmd = generation.claude_command(folder, archive, session_id)
    cmd[cmd.index("--effort") + 1] = "low"
    result = generation.wp2.run_claude(cmd, folder, archive, "stream", timeout=1800)
    generation.wp2.copy_transcript(folder, session_id, archive)
    calls = summarise_stream(archive / "stream.jsonl")
    summary = {"claude_version": claude_version(), "command": cmd, **result, "tool_calls": calls}
    (archive / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: summary[k] for k in ("claude_version", "models", "exit", "num_turns")}))
    for call in calls:
        print(
            f"{call['tool']:28s} error={call.get('is_error')!s:5s} -> {call.get('result', '')[:90]}"
        )
    print("\nfinal answer:\n" + str(result.get("result", "")))


if __name__ == "__main__":
    main()
