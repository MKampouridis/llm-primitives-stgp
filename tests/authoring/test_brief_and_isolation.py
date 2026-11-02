"""The arm-3 brief and session command: isolated, and free of arm-6 operators (D-062)."""

import json
import re
from types import SimpleNamespace

import pytest

from lpstgp.authoring import generation
from lpstgp.authoring.generation import DOMAINS, Slot
from lpstgp.operators.contract import CROSS_DOMAINS
from lpstgp.operators.registry import discover

DEV = SimpleNamespace(
    instruments={f"I{k:02d}": "x" for k in range(1, 22)},
    asset_class={f"I{k:02d}": ("equity_index", "fx", "commodity")[k % 3] for k in range(1, 22)},
)
# The plan's example operators (Method §1) and the arm-6 operators, in plain words.
PLAN_EXAMPLES = (
    "spectral entropy", "hurst", "lévy area", "levy area", "fisher–rao", "fisher-rao",
    "wasserstein", "rate–distortion", "rate-distortion", "fisher-information",
    "critical slowing", "volatility autocorrelation",
)  # fmt: skip
ARM6 = [s.name for s in discover().operators.values() if s.domain in CROSS_DOMAINS]
INSTRUMENT_WORDS = ("SPX", "S&P", "Nikkei", "EURUSD", "gold", "bitcoin", "DAX", "Brent")


def briefs():
    earlier = [{"domain": "spectral analysis", "signature": "x(Series) -> Real", "summary": "s"}]
    for domain in DOMAINS:
        yield domain, generation.render_brief(Slot(domain), earlier, {"Power": (0.5, 2.0)}, DEV)


def test_scopes_drop_wp2_examples():
    for domain, (_, scope) in DOMAINS.items():
        assert "for example" not in scope, domain
        assert "(" not in scope, domain
        assert scope.endswith(".")


@pytest.mark.parametrize(("domain", "brief"), list(briefs()), ids=list(DOMAINS))
def test_brief_names_no_arm6_or_plan_example_operator(domain, brief):
    text = brief.lower()
    for term in PLAN_EXAMPLES:
        assert term not in text, term
    for name in ARM6:
        assert name not in text, name
        assert name.replace("_", " ") not in text, name
    for word in INSTRUMENT_WORDS:
        assert not re.search(rf"\b{re.escape(word.lower())}\b", text), word
    assert not re.search(r"\b(19|20)\d\d\b", brief), "no dates or years"
    assert "lpstgp" not in text
    assert "$" not in brief


def test_brief_has_the_contract_core_earlier_operators_and_kinds():
    brief = dict(briefs())["fractal"]
    assert "fractal analysis" in brief
    assert "four" in brief
    assert "rolling_hist(Series, window: Window) -> Hist" in brief
    assert "x(Series) -> Real" in brief
    assert "`Power` (0.5, 2.0)" in brief
    assert "21 instruments" in brief


def test_first_brief_has_no_earlier_operators():
    brief = generation.render_brief(Slot("information_theory"), [], {}, DEV)
    assert "You are the first" in brief
    assert "Kinds already declared" not in brief


def test_session_command_is_isolated_and_uses_the_authoring_tools(tmp_path):
    cmd = generation.claude_command(tmp_path / "folder", tmp_path / "archive", "sid")
    joined = " ".join(cmd)
    for flag in ("--restricted", "--strict-mcp-config", "--disable-slash-commands"):
        assert flag in cmd
    assert cmd[cmd.index("--tools") + 1] == "Read,Write,Edit,Glob,Grep"
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5"
    allowed = cmd[cmd.index("--allowedTools") + 1].split()
    assert "mcp__devtool__describe" in allowed
    assert "mcp__devtool__backtest" not in allowed
    config = json.loads((tmp_path / "archive" / "mcp.json").read_text())
    assert config["mcpServers"]["devtool"]["args"][1] == "lpstgp.authoring.mcp_tools"
    assert "backtest" not in joined


def test_session_folder_holds_only_the_brief_and_the_contract(tmp_path):
    folder = tmp_path / "f"
    generation.prepare_session(folder, "brief")
    assert sorted(p.name for p in folder.iterdir()) == ["BRIEF.md", "operator_api.py"]
    assert generation.GEN_ROOT.name == "work-sessions"


def test_slots_one_per_domain_with_one_rerun():
    assert next(Slot(d).name for d in DOMAINS) == "a01_information_theory"
    assert Slot("spectral", 2).name == "a07_spectral_rerun2"
    assert list(DOMAINS) == list(CROSS_DOMAINS)
