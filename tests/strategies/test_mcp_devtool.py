"""The generation MCP server: protocol, tools, budget and logging (real Tier A dev data)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOY = Path(__file__).parent / "fixtures" / "toy_trend.py"


class Client:
    def __init__(self, session: Path, archive: Path, budget: int = 2):
        cmd = [sys.executable, "-m", "lpstgp.strategies.mcp_devtool", "--session", str(session)]
        cmd += ["--archive", str(archive), "--budget", str(budget), "--max-checks", "3"]
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

    def notify(self, method):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, name, **arguments):
        reply = self.request("tools/call", {"name": name, "arguments": arguments})
        return json.loads(reply["result"]["content"][0]["text"]), reply["result"]["isError"]

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)


@pytest.mark.realdata
@pytest.mark.usefixtures("tier_a_dir")
def test_mcp_server_tools_budget_and_log(tmp_path):
    session, archive = tmp_path / "session", tmp_path / "archive"
    session.mkdir()
    (session / "strategy.py").write_text(TOY.read_text())
    client = Client(session, archive)
    try:
        init = client.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
        assert init["result"]["serverInfo"]["name"] == "devtool"
        client.notify("notifications/initialized")
        names = [t["name"] for t in client.request("tools/list")["result"]["tools"]]
        assert names == ["check", "backtest"]
        report, is_error = client.call("check")
        assert report["passed"], report
        assert not is_error
        result, _ = client.call("backtest", file="strategy.py")
        assert result["ok"]
        assert result["backtests_left"] == 1
        assert set(result["instruments"]) == {f"I{k:02d}" for k in range(1, 22)}
        assert not any("SPX" in json.dumps(v) for v in result["instruments"].values())
        client.call("backtest")
        spent, is_error = client.call("backtest")
        assert is_error
        assert "used up" in spent["error"]
        escape, is_error = client.call("check", file="../../etc/passwd")
        assert is_error
        assert "folder" in escape["error"]
        assert client.request("unknown/method")["error"]["code"] == -32601
    finally:
        client.close()
    log = [json.loads(line) for line in (archive / "evaluations.jsonl").read_text().splitlines()]
    assert [e["tool"] for e in log] == ["check", "backtest", "backtest"]
    assert all((archive / "versions" / e["version"]).exists() for e in log)
