"""MCP server (stdio) for a maintenance session: arm 3's tools plus the patch or rule checks.

Arms 4-grow and 4-full: ``check`` and ``describe`` (as arm 3, on the anonymised development
window, D-036) and ``check_patch`` (how the host reads the folder's changes, with the arm's bounds,
the cap and the prune rule). Arm 5: ``check_rules`` (parse and type-check ``rules.json``). The
session's context (arm, state, the folder's initial files, the evidence the prune rule uses) is
read from ``<archive>/context.json``, written by the host before the session. Every call is
budgeted and logged to ``<archive>/evaluations.jsonl``.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpstgp.authoring.mcp_tools import TOOLS as AUTHORING_TOOLS
from lpstgp.authoring.mcp_tools import AuthoringServer
from lpstgp.strategies.mcp_devtool import serve

NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}
EXTRA_TOOLS = {
    "check_patch": {
        "name": "check_patch",
        "description": (
            "Show how your folder's changes will be read as a patch (grows, refines, prunes) "
            "and whether it meets this cycle's bounds, the library cap and the prune rule. "
            "It does not run the admission checks on each file: use check for that. "
            "Up to {max_check_patchs} calls."
        ),
        "inputSchema": NO_ARGS,
    },
    "check_rules": {
        "name": "check_rules",
        "description": (
            "Parse and type-check the rule pairs in rules.json against the primitive set and "
            "the tree limits; lists the pairs that would be discarded and why. "
            "Up to {max_check_ruless} calls."
        ),
        "inputSchema": NO_ARGS,
    },
}
ARM_TOOLS = {
    "4-grow": ("check", "describe", "check_patch"),
    "4-full": ("check", "describe", "check_patch"),
    "5": ("check_rules",),
}
LIMITS = {"check": 100, "describe": 50, "check_patch": 30, "check_rules": 30}


class MaintenanceServer(AuthoringServer):
    def __init__(self, session: Path, archive: Path, context: dict[str, Any]):
        super().__init__(session, archive, LIMITS["check"], LIMITS["describe"])
        self.context = context
        self.tools = ARM_TOOLS[context["arm"]]
        for tool in ("check_patch", "check_rules"):  # counted from the log by the base class
            self.limits[tool] = LIMITS[tool]
            self.used.setdefault(tool, 0)

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool not in self.tools:
            raise ValueError(f"unknown tool {tool}")
        if tool in ("check", "describe"):
            return super().call(tool, arguments)
        with self.lock:
            if self.used[tool] >= self.limits[tool]:
                return {
                    "ok": False,
                    "error": f"the {tool} budget of {self.limits[tool]} is used up",
                }
            self.used[tool] += 1
            result = self._check_patch() if tool == "check_patch" else self._check_rules()
            result[f"{tool}_calls_left"] = self.limits[tool] - self.used[tool]
            entry = {
                "n": sum(self.used.values()),
                "tool": tool,
                "utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "result": result,
            }
            with (self.archive / "evaluations.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(entry, default=float) + "\n")
            return result

    def _check_patch(self) -> dict[str, Any]:
        from lpstgp.maintenance import patch, state

        c = self.context
        current = state.read(c["state_id"], Path(c["results_dir"]))
        p = patch.read_patch(
            self.session, c["arm"], current, c["initial"], c["initial_sha"],
            c["evidence"], c.get("previous_evidence"), current.meta.get("retired", ()),
            self.archive / "jobs" / "patch", gates=False,
        )  # fmt: skip
        return {
            "ok": True,
            "grows": [r["operator"]["name"] for r in p.grows],
            "refines": [r["operator"]["name"] for r in p.refines],
            "prunes": p.prunes,
            "problems": p.problems,
            "meets_bounds_and_rules": p.admissible,
        }

    def _check_rules(self) -> dict[str, Any]:
        from lpstgp import libraries
        from lpstgp.config import load_settings
        from lpstgp.gp.pset import build
        from lpstgp.maintenance import rules
        from lpstgp.runner import configs_from_settings

        lib = build(libraries.resolve(self.context["library"]))
        limits = configs_from_settings(load_settings())[0].limits
        admitted, problems = rules.check_rules(self.session / rules.RULES_FILE, lib, limits)
        return {"ok": True, **rules.report(admitted, problems)}


def tool_list(arm: str, limits: dict[str, int]) -> list[dict]:
    known = {t["name"]: t for t in AUTHORING_TOOLS} | EXTRA_TOOLS
    fill = {f"max_{k}s": v for k, v in limits.items()}
    return [
        {**known[n], "description": known[n]["description"].format(**fill)} for n in ARM_TOOLS[arm]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    context = json.loads((args.archive / "context.json").read_text(encoding="utf-8"))
    server = MaintenanceServer(args.session, args.archive, context)
    serve(server, tool_list(context["arm"], server.limits))


if __name__ == "__main__":
    main()
