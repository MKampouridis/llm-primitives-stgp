"""The authoring MCP server: protocol, tools, budgets and log (real Tier A dev-fit data)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lpstgp.authoring import operator_api

FIX = Path(__file__).parent / "fixtures"


class Client:
    def __init__(self, session: Path, archive: Path):
        cmd = [sys.executable, "-m", "lpstgp.authoring.mcp_tools", "--session", str(session)]
        cmd += ["--archive", str(archive), "--max-checks", "2", "--max-describes", "1"]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        self.next_id = 0

    def request(self, method, params=None):
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def call(self, name, **arguments):
        reply = self.request("tools/call", {"name": name, "arguments": arguments})
        return json.loads(reply["result"]["content"][0]["text"]), reply["result"]["isError"]

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=60)


@pytest.mark.realdata
@pytest.mark.usefixtures("tier_a_dir")
def test_authoring_server_tools_budgets_and_log(tmp_path):
    session, archive = tmp_path / "session", tmp_path / "archive"
    session.mkdir()
    shutil.copyfile(operator_api.__file__, session / "operator_api.py")
    shutil.copyfile(FIX / "toy_operator.py", session / "toy_tstat.py")
    shutil.copyfile(FIX / "new_kind.py", session / "toy_concentration.py")
    client = Client(session, archive)
    try:
        init = client.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
        assert init["result"]["capabilities"] == {"tools": {}}
        names = [t["name"] for t in client.request("tools/list")["result"]["tools"]]
        assert names == ["check", "describe"]
        report, is_error = client.call("check", file="toy_tstat.py")
        assert report["passed"], report
        assert not is_error
        assert report["check_calls_left"] == 1
        described, _ = client.call("describe", file="toy_tstat.py")
        assert described["ok"]
        assert described["instruments"] >= 20
        assert "toy_concentration" in described["rank_correlation_with_other_operators"]
        text = json.dumps(described).lower()
        for word in ("sharpe", "return", "profit", "drawdown"):  # descriptive only
            assert word not in text
        refused, is_error = client.call("describe", file="toy_tstat.py")
        assert is_error
        assert "used up" in refused["error"]
        outside, is_error = client.call("check", file="operator_api.py")
        assert is_error
        assert "operator .py files" in outside["error"]
    finally:
        client.close()
    log = [json.loads(line) for line in (archive / "evaluations.jsonl").read_text().splitlines()]
    assert [e["tool"] for e in log] == ["check", "describe"]
    assert all((archive / "versions" / e["version"]).exists() for e in log)
