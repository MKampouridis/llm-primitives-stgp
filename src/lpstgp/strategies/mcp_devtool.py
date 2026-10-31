"""MCP server (stdio) giving a generation session its only two actions on data: check, backtest.

Started by Claude Code from the session's ``--mcp-config``. It runs on the host with access to
the repository and the capped data store; the agent's code is executed only through
``strategies.execute`` (sandboxed subprocess). Each call is logged, with a copy of the submitted
file, to ``<archive>/evaluations.jsonl``; backtests are budgeted.

Protocol: JSON-RPC 2.0, one JSON message per line (MCP stdio transport). Logs go to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpstgp.config import load_paths, load_settings
from lpstgp.runner import configs_from_settings
from lpstgp.splits import Stage
from lpstgp.strategies import devtool

TOOLS = [
    {
        "name": "check",
        "description": (
            "Run the admission checks on a strategy file in your folder (contract, source "
            "policy, determinism, no look-ahead, lookback, finite and non-degenerate output). "
            "Reports problems only, no performance. Free, up to {max_checks} calls."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "file name, default strategy.py"}
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "backtest",
        "description": (
            "Backtest a strategy file on the development data: per-instrument and aggregate "
            "metrics, including the objective. Each call uses one of your {budget} backtests."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "file name, default strategy.py"}
            },
            "additionalProperties": False,
        },
    },
]


class DevToolServer:
    def __init__(self, session: Path, archive: Path, budget: int, max_checks: int) -> None:
        self.session = session.resolve()
        self.archive = archive
        self.budget = budget
        self.max_checks = max_checks
        self.used = {"check": 0, "backtest": 0}
        self.lock = threading.Lock()
        paths, settings = load_paths(), load_settings()
        _, self.fitness = configs_from_settings(settings)
        self.dev = devtool.build(paths, settings, Stage.FIT, archive / "inputs")
        (archive / "versions").mkdir(parents=True, exist_ok=True)

    def _file(self, name: str | None) -> Path:
        path = (self.session / (name or "strategy.py")).resolve()
        if path.parent != self.session or path.suffix != ".py":
            raise ValueError("give the name of a .py file in your folder, e.g. strategy.py")
        if not path.is_file():
            raise ValueError(f"{path.name} does not exist in your folder")
        return path

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if tool not in self.used:
                raise ValueError(f"unknown tool {tool}")
            limit = self.budget if tool == "backtest" else self.max_checks
            if self.used[tool] >= limit:
                return {"ok": False, "error": f"the {tool} budget of {limit} calls is used up"}
            path = self._file(arguments.get("file"))
            self.used[tool] += 1
            n = sum(self.used.values())
            version = self.archive / "versions" / f"{n:03d}_{tool}.py"
            shutil.copyfile(path, version)
            job = self.archive / "jobs" / f"{n:03d}"
            if tool == "check":
                result = devtool.check(version, job, self.dev)
            else:
                result = devtool.backtest(version, job, self.dev, self.fitness)
                result["backtests_used"] = self.used["backtest"]
                result["backtests_left"] = self.budget - self.used["backtest"]
            shutil.rmtree(job, ignore_errors=True)
            entry = {
                "n": n,
                "tool": tool,
                "utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "file": path.name,
                "sha256": hashlib.sha256(version.read_bytes()).hexdigest(),
                "version": version.name,
                "result": result,
            }
            with (self.archive / "evaluations.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(entry, default=float) + "\n")
            return result


def _respond(message_id: Any, result: Any = None, error: dict | None = None) -> None:
    payload = {"jsonrpc": "2.0", "id": message_id}
    payload["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(payload, default=float) + "\n")
    sys.stdout.flush()


def serve(server: DevToolServer) -> None:
    tools = [
        {
            **t,
            "description": t["description"].format(
                budget=server.budget, max_checks=server.max_checks
            ),
        }
        for t in TOOLS
    ]
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        method, message_id = message.get("method"), message.get("id")
        if message_id is None:  # notification
            continue
        if method == "initialize":
            version = message.get("params", {}).get("protocolVersion", "2025-06-18")
            _respond(
                message_id,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "devtool", "version": "1"},
                },
            )
        elif method == "ping":
            _respond(message_id, {})
        elif method == "tools/list":
            _respond(message_id, {"tools": tools})
        elif method == "tools/call":
            params = message.get("params", {})
            try:
                result = server.call(params.get("name", ""), params.get("arguments") or {})
                text, is_error = json.dumps(result, default=float), not result.get("ok", False)
            except Exception as exc:  # tool errors go back to the agent, never crash the server
                text, is_error = json.dumps({"ok": False, "error": str(exc)}), True
            _respond(message_id, {"content": [{"type": "text", "text": text}], "isError": is_error})
        else:
            _respond(message_id, error={"code": -32601, "message": f"method {method} not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=40)
    parser.add_argument("--max-checks", type=int, default=100)
    args = parser.parse_args()
    serve(DevToolServer(args.session, args.archive, args.budget, args.max_checks))


if __name__ == "__main__":
    main()
