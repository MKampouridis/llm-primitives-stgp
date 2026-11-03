"""MCP server (stdio) for an operator-authoring session: ``check`` and ``describe`` (D-062).

Started by Claude Code from the session's ``--mcp-config``. It runs on the host; the agent's code
runs only in the sandboxed worker (``lpstgp.authoring.worker`` through ``strategies.execute``).
Data are the anonymised development window's FIT stage (dev-fit, D-036), as in WP2. There is no
backtest: neither tool reports performance. Every call is logged with a copy of the file to
``<archive>/evaluations.jsonl``, and both tools are budgeted (a resumed session keeps its count).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpstgp.config import load_paths, load_settings
from lpstgp.splits import Stage
from lpstgp.strategies import devtool, execute
from lpstgp.strategies.mcp_devtool import serve

WORKER = "lpstgp.authoring.worker"
API_FILE = "operator_api.py"
TOOLS = [
    {
        "name": "check",
        "description": (
            "Run the admission checks on an operator file in your folder: source rules, contract, "
            "type, finite and non-constant output, determinism, no look-ahead, exact lookback, "
            "declared invariances, runtime, and finite non-constant output on the development "
            "data. Reports problems only. Up to {max_checks} calls."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string", "description": "operator file name"}},
            "required": ["file"],
            "additionalProperties": False,
        },
    },
    {
        "name": "describe",
        "description": (
            "Descriptive statistics of an operator's output on the development data, at several "
            "grid points: finite share, quantiles, lag-1 autocorrelation, share of distinct "
            "values, and rank correlation with the other operator files in your folder (medians "
            "across instruments). Only for a file whose current version has passed check. No "
            "performance figures. Up to {max_describes} calls."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"file": {"type": "string", "description": "operator file name"}},
            "required": ["file"],
            "additionalProperties": False,
        },
    },
]


def check(path: Path, job: Path, dev: devtool.DevData) -> dict[str, Any]:
    report = execute.run("gates", path, job, inputs_path=dev.inputs_path, worker=WORKER)
    if not report.get("ok"):
        return report
    failures = [r for r in report["results"] if not r["passed"]]
    return {
        "ok": True,
        "passed": report["passed"],
        "checks": len(report["results"]),
        "failures": failures[:20],
    }


def describe(path: Path, job: Path, dev: devtool.DevData, others: list[Path]) -> dict[str, Any]:
    return execute.run(
        "describe", path, job, inputs_path=dev.inputs_path, worker=WORKER, extra=tuple(others)
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operator_files(session: Path) -> list[Path]:
    return sorted(p for p in session.glob("*.py") if p.name != API_FILE)


class AuthoringServer:
    def __init__(self, session: Path, archive: Path, max_checks: int, max_describes: int):
        self.session = session.resolve()
        self.archive = archive
        self.limits = {"check": max_checks, "describe": max_describes}
        self.used = {"check": 0, "describe": 0}
        self.lock = threading.Lock()
        paths, settings = load_paths(), load_settings()
        self.dev = devtool.build(paths, settings, Stage.FIT, archive / "inputs")
        (archive / "versions").mkdir(parents=True, exist_ok=True)
        log = archive / "evaluations.jsonl"
        if log.exists():
            for line in log.read_text(encoding="utf-8").splitlines():
                tool = json.loads(line)["tool"]
                self.used[tool] = self.used.get(tool, 0) + 1

    def _passed(self) -> set[str]:
        """Hashes of the file versions that passed ``check`` in this session."""
        log = self.archive / "evaluations.jsonl"
        if not log.exists():
            return set()
        out = set()
        for line in log.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["tool"] == "check" and entry["result"].get("passed"):
                out.add(entry["sha256"])
        return out

    def _file(self, name: str | None) -> Path:
        if not name:
            raise ValueError("give the name of an operator file in your folder")
        path = (self.session / name).resolve()
        if path.parent != self.session or path.suffix != ".py" or path.name == API_FILE:
            raise ValueError("give the name of one of your operator .py files in your folder")
        if not path.is_file():
            raise ValueError(f"{path.name} does not exist in your folder")
        return path

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if tool not in self.used:
                raise ValueError(f"unknown tool {tool}")
            if self.used[tool] >= self.limits[tool]:
                return {
                    "ok": False,
                    "error": f"the {tool} budget of {self.limits[tool]} is used up",
                }
            path = self._file(arguments.get("file"))
            if tool == "describe" and _sha(path) not in self._passed():
                return {  # real-data statistics only for code that passed every gate (D-074)
                    "ok": False,
                    "error": "describe works only on a file whose current version has passed "
                    "check; run check on it first (no describe call was used)",
                }
            self.used[tool] += 1
            n = sum(self.used.values())
            version = self.archive / "versions" / f"{n:03d}_{tool}_{path.name}"
            shutil.copyfile(path, version)
            job = self.archive / "jobs" / f"{n:03d}"
            if tool == "check":
                result = check(version, job, self.dev)
            else:
                others = [p for p in operator_files(self.session) if p != path]
                result = describe(version, job, self.dev, others)
            result[f"{tool}_calls_left"] = self.limits[tool] - self.used[tool]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--max-checks", type=int, default=100)
    parser.add_argument("--max-describes", type=int, default=50)
    args = parser.parse_args()
    server = AuthoringServer(args.session, args.archive, args.max_checks, args.max_describes)
    tools = [
        {
            **t,
            "description": t["description"].format(
                **{f"max_{k}s": v for k, v in server.limits.items()}
            ),
        }
        for t in TOOLS
    ]
    serve(server, tools)


if __name__ == "__main__":
    main()
