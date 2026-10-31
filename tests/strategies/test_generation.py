"""Generation harness (offline): slots, brief, isolation flags, environment, transcript parsing."""

import json
from pathlib import Path

from lpstgp.gp.fitness import FitnessConfig
from lpstgp.splits import Stage
from lpstgp.strategies import generation
from lpstgp.strategies.devtool import DevData
from lpstgp.strategies.generation import Slot

DEV = DevData(
    Stage.FIT,
    Path("unused.npz"),
    {"I01": "A", "I02": "B", "I03": "C"},
    {"I01": "equity_index", "I02": "fx", "I03": "fx"},
    {},
)
# Distinctive phrases of LLQ's published prompt (andrewclayman/LLQ_CIFEr); our brief must not reuse them.
LLQ_PHRASES = (
    "ABSOLUTELY NO PEEKING",
    "SINGLE SOURCE OF TRUTH",
    "vectorbt",
    "Large Language Quant",
    "LLQ",
)


def test_slots_cover_seven_domains_four_each():
    slots = generation.all_slots()
    assert len(slots) == 28
    assert [s.sid for s in slots] == [f"s{k:02d}" for k in range(1, 29)]
    assert Slot("optimal_transport", 1).sid == "s09"


def test_brief_is_complete_and_original():
    earlier = [{"name": "w1_shift", "hypothesis": "Distribution shifts precede reversals."}]
    brief = generation.render_brief(
        Slot("optimal_transport", 2), earlier, vars(FitnessConfig()), DEV
    )
    assert "optimal transport" in brief
    assert "**w1_shift**: Distribution shifts precede reversals." in brief
    assert "40 backtests" in brief
    assert "0.5 × median(drawdown / volatility)" in brief
    assert "3 instruments (1 equity indices, 2 currency pairs)" in brief
    assert "$" not in brief
    for phrase in LLQ_PHRASES:
        assert phrase.lower() not in brief.lower()
    first = generation.render_brief(Slot("fractal", 1), [], vars(FitnessConfig()), DEV)
    assert "You are the first to work on this field." in first


def test_session_command_is_isolated(tmp_path):
    cmd = generation.claude_command(
        tmp_path / "s", tmp_path / "a", "00000000-0000-0000-0000-000000000000"
    )
    for flag in ("--restricted", "--strict-mcp-config", "--disable-slash-commands"):
        assert flag in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    tools = cmd[cmd.index("--tools") + 1].split(",")
    assert "Bash" not in tools
    assert not {"WebFetch", "WebSearch", "Agent", "Task"} & set(tools)
    assert "--fallback-model" not in cmd
    assert not any("dangerously" in part for part in cmd)
    servers = json.loads((tmp_path / "a" / "mcp.json").read_text())["mcpServers"]
    assert list(servers) == ["devtool"]


def test_session_environment_has_no_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("SOME_SECRET", "x")
    env = generation.session_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "SOME_SECRET" not in env
    assert env["DISABLE_AUTOUPDATER"] == "1"


def test_usage_reads_models_and_result(tmp_path):
    stream = tmp_path / "s.jsonl"
    events = [
        {"type": "system", "subtype": "init", "message": "hello"},
        {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": []}},
        {
            "type": "result",
            "subtype": "success",
            "num_turns": 3,
            "total_cost_usd": 0.5,
            "usage": {"output_tokens": 9},
        },
    ]
    stream.write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n")
    out = generation.usage(stream)
    assert out["models"] == ["claude-opus-5-5"]
    assert out["num_turns"] == 3
    assert out["usage"] == {"output_tokens": 9}
