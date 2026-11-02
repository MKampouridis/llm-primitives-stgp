"""Arm 3: one isolated headless Claude Code session per domain writes four operators (D-062).

As WP2's strategy generation (D-035): a fresh, neutrally named folder outside the repository
holds only ``BRIEF.md`` and ``operator_api.py``; the session's tools are the file tools (confined
to the folder) and the two MCP tools of :mod:`lpstgp.authoring.mcp_tools` (check, describe). It
has no shell, no web tools, no other MCP servers, no skills and none of the user's settings.
Agent code runs only in the sandboxed worker. Sessions run in domain order; each later brief
lists the operators already accepted in earlier domains. Everything is archived under
``results/wp3/arm3_authoring/<slot>/``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any

from lpstgp.authoring import mcp_tools, operator_api
from lpstgp.strategies import execute
from lpstgp.strategies import generation as wp2

PROMPTS = Path(__file__).resolve().parent / "prompts"
BRIEF = PROMPTS / "brief.md"
GEN_ROOT = Path.home() / "Library" / "Caches" / "work-sessions"
MODEL, EFFORT = wp2.MODEL, wp2.EFFORT
MAX_CHECKS, MAX_DESCRIBES = 100, 50
OPERATORS_PER_DOMAIN = 4
ALLOWED_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "mcp__devtool__check",
    "mcp__devtool__describe",
)


def domain_scope(domain: str) -> tuple[str, str]:
    """Title and scope of a domain: WP2's wording without its examples, which name arm-6
    operators (D-062)."""
    title, scope = wp2.DOMAINS[domain]
    return title, re.sub(r"\s*\(for example[^)]*\)", "", scope)


DOMAINS = {d: domain_scope(d) for d in wp2.DOMAINS}


@dataclass(frozen=True)
class Slot:
    domain: str
    attempt: int = 1  # 2 = the one fresh re-run of a failed slot

    @property
    def name(self) -> str:
        k = list(DOMAINS).index(self.domain) + 1
        return f"a{k:02d}_{self.domain}" + ("" if self.attempt == 1 else f"_rerun{self.attempt}")


def core_listing() -> str:
    """The shared data terminals and core glue, as the brief shows them."""
    from lpstgp.operators.registry import discover

    registry = discover()
    data, core = [], []
    for spec in sorted(registry.domain("data", "core"), key=lambda s: s.name):
        if hasattr(spec, "inputs"):
            args = [t.__name__ for t in spec.inputs]
            args += [f"{p.name}: {p.kind.__name__}" for p in spec.params]
            core.append(
                f"- `{spec.name}({', '.join(args)}) -> {spec.output.__name__}`: {spec.summary}"
            )
        else:
            data.append(f"- `{spec.name}` ({spec.output.__name__}): {spec.summary}")
    return "Data streams:\n\n" + "\n".join(data) + "\n\nCore operators:\n\n" + "\n".join(core)


def render_brief(
    slot: Slot,
    earlier: Sequence[Mapping[str, str]],
    kinds: Mapping[str, Sequence],
    dev,
    template: str | None = None,
) -> str:
    title, scope = DOMAINS[slot.domain]
    if earlier:
        lines = "\n".join(f"- `{e['signature']}` ({e['domain']}): {e['summary']}" for e in earlier)
        earlier_text = (
            "Operators already written for other fields (yours must not duplicate them):\n\n"
            + lines
        )
    else:
        earlier_text = "You are the first to write operators for this library."
    kinds_text = ""
    if kinds:
        listed = "; ".join(f"`{k}` {tuple(g)}" for k, g in sorted(kinds.items()))
        kinds_text = f"\n  Kinds already declared (reuse them with the same grid): {listed}."
    classes: dict[str, int] = {}
    for cls in dev.asset_class.values():
        classes[cls] = classes.get(cls, 0) + 1
    names = {"equity_index": "equity indices", "fx": "currency pairs", "commodity": "commodities"}
    mix = ", ".join(f"{n} {names.get(c, c)}" for c, n in sorted(classes.items()))
    return Template(template or BRIEF.read_text(encoding="utf-8")).substitute(
        domain_title=title,
        domain_scope=scope,
        core=core_listing(),
        earlier=earlier_text,
        kinds=kinds_text,
        max_lookback=operator_api.MAX_LOOKBACK,
        max_checks=MAX_CHECKS,
        max_describes=MAX_DESCRIBES,
        n_instruments=len(dev.instruments),
        class_mix=mix,
    )


def prepare_session(folder: Path, brief: str) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "BRIEF.md").write_text(brief, encoding="utf-8")
    shutil.copyfile(Path(operator_api.__file__), folder / mcp_tools.API_FILE)


def mcp_config(folder: Path, archive: Path) -> dict:
    args = ["-m", "lpstgp.authoring.mcp_tools", "--session", str(folder), "--archive", str(archive)]
    args += ["--max-checks", str(MAX_CHECKS), "--max-describes", str(MAX_DESCRIBES)]
    return {"mcpServers": {"devtool": {"type": "stdio", "command": sys.executable, "args": args}}}


def claude_command(
    folder: Path, archive: Path, session_id: str, resume: str | None = None
) -> list[str]:
    """WP2's isolated command, with this module's MCP server and tools."""
    cmd = wp2.claude_command(folder, archive, session_id, resume)
    (archive / "mcp.json").write_text(json.dumps(mcp_config(folder, archive), indent=1))
    cmd[cmd.index("--allowedTools") + 1] = " ".join(ALLOWED_TOOLS)
    return cmd


def _run(command: str, path: Path, job: Path, dev=None, threads: int = 1) -> dict:
    return execute.run(
        command,
        path,
        job,
        inputs_path=dev.inputs_path if dev else None,
        worker=mcp_tools.WORKER,
        threads=threads,
    )


def finalize(
    folder: Path,
    archive: Path,
    dev,
    taken: set[str],
    kinds: Mapping[str, Sequence],
) -> dict[str, Any]:
    """Gates and cross-process determinism of every operator file; ``taken`` are names in use."""
    files = mcp_tools.operator_files(folder)
    out: dict[str, Any] = {"files": [p.name for p in files], "operators": []}
    problems: list[str] = []
    if len(files) != OPERATORS_PER_DOMAIN:
        problems.append(f"{len(files)} operator files; exactly {OPERATORS_PER_DOMAIN} are needed")
    final = archive / "final"
    final.mkdir(parents=True, exist_ok=True)
    names: set[str] = set()
    declared = {k: tuple(v) for k, v in kinds.items()}
    for path in files:
        shutil.copyfile(path, final / path.name)
        work = archive / "final_jobs" / path.stem
        meta = _run("meta", final / path.name, work / "meta")
        if not meta.get("ok"):
            problems.append(f"{path.name}: {meta.get('error')}")
            continue
        op = meta["operator"]
        gates = _run("gates", final / path.name, work / "gates", dev)
        hashes = [
            _run("hash", final / path.name, work / f"hash{t}", threads=t).get("hash")
            for t in (1, 4)
        ]
        row = {
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "operator": op,
            "gates_passed": bool(gates.get("passed")),
            "gate_failures": [r for r in gates.get("results", []) if not r["passed"]][:20]
            or ([gates.get("error")] if not gates.get("ok") else []),
            "cross_process_deterministic": hashes[0] is not None and hashes[0] == hashes[1],
        }
        out["operators"].append(row)
        if not row["gates_passed"]:
            problems.append(f"{path.name}: fails check")
        if not row["cross_process_deterministic"]:
            problems.append(f"{path.name}: output differs across processes or thread counts")
        if op["name"] in taken or op["name"] in names:
            problems.append(f"{path.name}: the name {op['name']} is already in use")
        names.add(op["name"])
        for p in op["params"].values():
            kind = p["kind"].removeprefix("Llm")
            if p["kind"].startswith("Llm"):
                if kind in declared and declared[kind] != tuple(p["grid"]):
                    problems.append(f"{path.name}: kind {kind} has another grid elsewhere")
                declared.setdefault(kind, tuple(p["grid"]))
    shutil.rmtree(archive / "final_jobs", ignore_errors=True)
    out["problems"] = problems
    out["accepted"] = not problems
    out["kinds"] = {k: list(v) for k, v in declared.items()}
    return out


def run_session(
    slot: Slot,
    earlier: Sequence[Mapping[str, str]],
    kinds: Mapping[str, Sequence],
    taken: set[str],
    root: Path,
    archive_root: Path,
    paths,
    settings,
    timeout: float = 3 * 3600,
    claude_version: str = "",
) -> dict[str, Any]:
    """One authoring session, resumable; repaired once if its final files fail (as WP2)."""
    from lpstgp.data.tier_a import git_revision
    from lpstgp.splits import Stage
    from lpstgp.strategies import devtool

    archive = archive_root / slot.name
    archive.mkdir(parents=True, exist_ok=True)
    state = archive / "session.json"
    dev = devtool.build(paths, settings, Stage.FIT, archive / "inputs")
    record: dict[str, Any]

    def save() -> None:
        state.write_text(json.dumps(record, indent=1, default=float), encoding="utf-8")

    if state.exists():
        record = json.loads(state.read_text(encoding="utf-8"))
        folder, session_id = Path(record["folder"]), record["session_id"]
    else:
        template = BRIEF.read_text(encoding="utf-8")
        brief = render_brief(slot, earlier, kinds, dev, template)
        session_id = str(uuid.uuid4())
        folder = root / session_id
        prepare_session(folder, brief)
        record = {
            "slot": slot.name,
            "domain": slot.domain,
            "attempt": slot.attempt,
            "session_id": session_id,
            "folder": str(folder),
            "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": MODEL,
            "effort": EFFORT,
            "limits": {"check": MAX_CHECKS, "describe": MAX_DESCRIBES},
            "claude_version": claude_version,
            "code_version": git_revision(),
            "brief_template_sha12": wp2.sha12(template),
            "brief_sha12": wp2.sha12(brief),
            "earlier": list(earlier),
            "runs": [],
        }
        (archive / "BRIEF.md").write_text(brief, encoding="utf-8")
        record["command"] = claude_command(folder, archive, session_id)
        save()
    if not record["runs"]:
        record["runs"].append(wp2.run_claude(record["command"], folder, archive, "stream", timeout))
        save()
    while not wp2.completed(record["runs"][-1]):
        last = record["runs"][-1]
        waits = sum(1 for r in record["runs"] if wp2.limited(r))
        failures = sum(1 for r in record["runs"] if not wp2.limited(r) and not wp2.completed(r))
        if waits > wp2.LIMIT_WAITS or failures > wp2.MAX_RESUMES:
            break
        time.sleep(wp2.seconds_until_reset(last) if wp2.limited(last) else wp2.RESUME_WAIT_S)
        cmd = claude_command(folder, archive, session_id, resume=wp2.RESUME_PROMPT)
        record["runs"].append(
            wp2.run_claude(cmd, folder, archive, f"resume{len(record['runs'])}", timeout)
        )
        save()
    if not wp2.completed(record["runs"][-1]):
        record.update({"accepted": False, "reason": "session did not complete"})
        (archive / "summary.json").write_text(json.dumps(record, indent=1, default=float))
        return record
    result = finalize(folder, archive, dev, taken, kinds)
    if not result["accepted"]:
        repair = (
            "The final checks failed. Fix your operator files so that exactly "
            f"{OPERATORS_PER_DOMAIN} files, one operator each, pass check (you may run check "
            "again within your remaining calls). Problems:\n"
            + json.dumps(result["problems"], default=str)[:2000]
            + "\nDetails:\n"
            + json.dumps([o["gate_failures"] for o in result["operators"]], default=str)[:3000]
        )
        cmd = claude_command(folder, archive, session_id, resume=repair)
        record["runs"].append(wp2.run_claude(cmd, folder, archive, "repair", timeout / 2))
        result = finalize(folder, archive, dev, taken, kinds)
        result["repaired"] = True
    wp2.copy_transcript(folder, session_id, archive)
    models = sorted({m for run in record["runs"] for m in run.get("models", [])})
    if models != [MODEL]:
        result.update({"accepted": False, "reason": f"models used: {models}"})
    record.update(result)
    record["finished_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    shutil.rmtree(archive / "inputs", ignore_errors=True)
    (archive / "summary.json").write_text(
        json.dumps(record, indent=1, default=float), encoding="utf-8"
    )
    return record
