"""The LLM session of a maintenance cycle: brief, folder, isolated headless run (protocol_wp3 §4).

The session is isolated as in WP2 and arm 3 (D-035, D-062): a fresh, neutrally named folder
outside the repository, file tools confined to it, our MCP tools only, no shell, web, settings,
memory or skills, model ``claude-opus-5-5`` at effort high on the subscription. Arms 4-grow,
4-full and 5 get the same evidence, the same model, effort and session limits (H4's matched LLM
budget); they differ in what they may change: the library's files (arms 4) or ``rules.json``
(arm 5). Everything is archived under the cycle's folder in ``results/wp3/``.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any

from lpstgp.authoring import generation as authoring
from lpstgp.authoring import operator_api
from lpstgp.authoring.mcp_tools import API_FILE
from lpstgp.gp.pset import PrimitiveLibrary
from lpstgp.maintenance import evidence, mcp_tools, patch, rules
from lpstgp.operators.contract import OperatorSpec
from lpstgp.strategies import generation as wp2

PROMPTS = Path(__file__).resolve().parent / "prompts"
GEN_ROOT = authoring.GEN_ROOT
MODEL, EFFORT = wp2.MODEL, wp2.EFFORT
CLASS_NAMES = {"equity_index": "equity indices", "fx": "currency pairs", "commodity": "commodities"}
TASKS = {
    "4-grow": "you may add new operators to the library.",
    "4-full": "you may add new operators, refine existing ones and prune unhelpful ones.",
}


def allowed_tools(arm: str) -> tuple[str, ...]:
    base = ("Read", "Write", "Edit", "Glob", "Grep")
    return base + tuple(f"mcp__devtool__{t}" for t in mcp_tools.ARM_TOOLS[arm])


def class_mix(asset_class: Mapping[str, str]) -> str:
    counts = Counter(asset_class.values())
    return ", ".join(f"{n} {CLASS_NAMES.get(c, c)}" for c, n in sorted(counts.items()))


def domains_listing() -> str:
    return "\n".join(f"- `{d}` ({t}): {s}" for d, (t, s) in authoring.DOMAINS.items())


def node_signature(spec: OperatorSpec) -> str:
    args = [t.__name__ for t in spec.inputs] + [p.kind.__name__ for p in spec.params]
    return f"{spec.gp_name}({', '.join(args)}) -> {spec.output.__name__}"


def core_listing(lib: PrimitiveLibrary) -> str:
    data, core = [], []
    for name, spec in sorted(lib.terminals.items()):
        data.append(f"- `{name}` ({spec.output.__name__}): {spec.summary}")
    for _name, spec in sorted(lib.operators.items()):
        if spec.domain == "core":
            core.append(f"- `{node_signature(spec)}`: {spec.summary}")
    return "Data streams:\n\n" + "\n".join(data) + "\n\nCore:\n\n" + "\n".join(core)


def library_listing(lib: PrimitiveLibrary) -> str:
    lines = []
    for _name, spec in sorted(lib.operators.items(), key=lambda kv: (kv[1].domain, kv[1].name)):
        if spec.domain == "core":
            continue
        lines.append(
            f"- `{spec.name}` v{spec.version} [`{node_signature(spec)}`] ({spec.domain}): "
            f"{spec.summary}"
        )
    return "\n".join(lines)


def params_listing(lib: PrimitiveLibrary) -> str:
    by_kind: dict[str, list[str]] = {}
    for label, (kind, _value) in lib.params.items():
        by_kind.setdefault(kind.__name__, []).append(f"`{label}`")
    return "\n".join(f"- {k}: {', '.join(v)}" for k, v in sorted(by_kind.items()))


def elite_listing(elite: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for k, e in enumerate(elite, 1):
        lines.append(
            f"{k}. ({CLASS_NAMES.get(e['asset_class'], e['asset_class'])}, training fitness "
            f"{e['fit_fitness']:.3f})\n   entry: `{e['entry']}`\n   exit: `{e['exit']}`"
        )
    return "\n".join(lines)


def summary_text(s: Mapping[str, Any]) -> str:
    med = s.get("median_fit_fitness")
    nt = s.get("no_trade_share")
    return (
        f"Runs: {s['runs']}. Median training fitness of the runs' best rules: "
        f"{'–' if med is None else f'{med:.3f}'}; share of best rules that never trade: "
        f"{'–' if nt is None else f'{nt:.3f}'}."
    )


def outcome_text(last: Mapping[str, Any] | None) -> str:
    """The previous cycle's outcome, without any validation figure (D-071)."""
    if not last:
        return "This is the first cycle: no earlier change to report."
    what = last.get("what", "a change")
    if last.get("status") == "admitted":
        return f"Last cycle's {what} was admitted; the evidence above is for the changed library."
    if last.get("status") == "none":
        return "Last cycle made no change."
    reason = last.get("reason", "")
    return f"Last cycle's {what} was rejected ({reason}); the library stayed as it was."


def render(
    arm: str,
    lib: PrimitiveLibrary,
    rows: Mapping[str, Mapping],
    history: Mapping[str, Sequence],
    summary: Mapping[str, Any],
    elite: Sequence[Mapping[str, Any]],
    last: Mapping[str, Any] | None,
    asset_class: Mapping[str, str],
    runs_per_instrument: int,
    gp_cfg,
) -> str:
    common = {
        "domains": domains_listing(),
        "n_runs": summary["runs"],
        "n_instruments": len(asset_class),
        "class_mix": class_mix(asset_class),
        "runs_per_instrument": runs_per_instrument,
        "core": core_listing(lib),
        "library": library_listing(lib),
        "summary": summary_text(summary),
        "evidence": evidence.render_table(rows, history),
        "n_elite": len(elite),
        "elite": elite_listing(elite),
        "last_outcome": outcome_text(last),
        "max_lookback": min(gp_cfg.limits.lookback_max, operator_api.MAX_LOOKBACK),
    }
    if arm == "5":
        template = (PROMPTS / "propose.md").read_text(encoding="utf-8")
        return Template(template).substitute(
            common,
            max_rules=rules.MAX_RULES,
            population=gp_cfg.population,
            params=params_listing(lib),
            max_depth=gp_cfg.limits.max_depth,
            max_nodes=gp_cfg.limits.max_nodes,
            max_check_rules=mcp_tools.LIMITS["check_rules"],
        )
    b = patch.BOUNDS[arm]
    allowed = [f"- grow: up to {b['grow']} new operators"]
    if b["refine"]:
        allowed.append(f"- refine: up to {b['refine']} existing operators (a new version)")
    if b["prune"]:
        allowed.append(
            f"- prune: up to {b['prune']} operators, only if usage is at most "
            f"{evidence.PRUNE_MAX_USAGE} and contribution at most "
            f"{evidence.PRUNE_MAX_CONTRIBUTION} (or `–`) in this cycle and the previous one"
        )
    allowed.append(f"- the library may hold at most {patch.LIBRARY_CAP} of these operators")
    refine_prune = ""
    if b["refine"]:
        refine_prune += (
            "\n- **Refine**: edit an operator's file; it must still define the same operator "
            "name. The host stores it as a new version."
        )
    if b["prune"]:
        refine_prune += (
            "\n- **Prune**: empty the operator's file (leave it with no content); you cannot "
            "delete files."
        )
    template = (PROMPTS / "maintain.md").read_text(encoding="utf-8")
    return Template(template).substitute(
        common,
        task=TASKS[arm],
        allowed="This cycle you may make at most:\n\n" + "\n".join(allowed),
        refine_prune=refine_prune,
        max_checks=mcp_tools.LIMITS["check"],
        max_describes=mcp_tools.LIMITS["describe"],
        max_check_patch=mcp_tools.LIMITS["check_patch"],
    )


def prepare(folder: Path, brief: str) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "BRIEF.md").write_text(brief, encoding="utf-8")
    shutil.copyfile(Path(operator_api.__file__), folder / API_FILE)


def mcp_config(folder: Path, archive: Path) -> dict:
    args = ["-m", "lpstgp.maintenance.mcp_tools", "--session", str(folder)]
    args += ["--archive", str(archive)]
    return {"mcpServers": {"devtool": {"type": "stdio", "command": sys.executable, "args": args}}}


def claude_command(
    arm: str, folder: Path, archive: Path, session_id: str, resume: str | None = None
) -> list[str]:
    cmd = wp2.claude_command(folder, archive, session_id, resume)
    (archive / "mcp.json").write_text(json.dumps(mcp_config(folder, archive), indent=1))
    cmd[cmd.index("--allowedTools") + 1] = " ".join(allowed_tools(arm))
    return cmd


def run(
    arm: str,
    archive: Path,
    brief: str,
    setup: Callable[[Path], None],
    finish: Callable[[Path], dict[str, Any]],
    repair_prompt: Callable[[dict[str, Any]], str | None],
    claude_version: str = "",
    timeout: float = 3 * 3600,
    root: Path = GEN_ROOT,
) -> dict[str, Any]:
    """One resumable session: ``setup`` fills the folder, ``finish`` reads the result, and a
    ``repair_prompt`` (None = no repair) gives the failed result one more turn."""
    from lpstgp.data.tier_a import git_revision

    archive.mkdir(parents=True, exist_ok=True)
    state = archive / "session.json"
    if state.exists():
        record = json.loads(state.read_text(encoding="utf-8"))
        folder, session_id = Path(record["folder"]), record["session_id"]
    else:
        session_id = str(uuid.uuid4())
        folder = root / session_id
        prepare(folder, brief)
        setup(folder)
        (archive / "BRIEF.md").write_text(brief, encoding="utf-8")
        record = {
            "arm": arm,
            "session_id": session_id,
            "folder": str(folder),
            "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": MODEL,
            "effort": EFFORT,
            "limits": {t: mcp_tools.LIMITS[t] for t in mcp_tools.ARM_TOOLS[arm]},
            "claude_version": claude_version,
            "code_version": git_revision(),
            "brief_sha12": wp2.sha12(brief),
            "runs": [],
        }
        record["command"] = claude_command(arm, folder, archive, session_id)
        state.write_text(json.dumps(record, indent=1, default=float), encoding="utf-8")

    def save() -> None:
        state.write_text(json.dumps(record, indent=1, default=float), encoding="utf-8")

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
        cmd = claude_command(arm, folder, archive, session_id, resume=wp2.RESUME_PROMPT)
        record["runs"].append(
            wp2.run_claude(cmd, folder, archive, f"resume{len(record['runs'])}", timeout)
        )
        save()
    if not wp2.completed(record["runs"][-1]):
        record.update({"completed": False, "result": None})
        save()
        return record
    result = finish(folder)
    prompt = repair_prompt(result)
    if prompt and not record.get("repaired"):
        cmd = claude_command(arm, folder, archive, session_id, resume=prompt)
        record["runs"].append(wp2.run_claude(cmd, folder, archive, "repair", timeout / 2))
        record["repaired"] = True
        result = finish(folder)
    wp2.copy_transcript(folder, session_id, archive)
    models = sorted({m for r in record["runs"] for m in r.get("models", [])})
    record.update(
        {
            "completed": True,
            "models": models,
            "model_ok": models == [MODEL],
            "result": result,
            "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    save()
    return record
