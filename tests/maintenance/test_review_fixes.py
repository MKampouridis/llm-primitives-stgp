"""Regression tests for the WP3 code review's findings (D-074); each reproduces the reported case."""

import json
import threading

import numpy as np
import pytest
from deap import gp as deap_gp
from tests.maintenance.conftest import problem_for
from tests.maintenance.test_states_patches_rules import folder_with_library, grow, results  # noqa: F401

from lpstgp import libraries
from lpstgp.authoring import gates, mcp_tools, worker
from lpstgp.gp.pset import build
from lpstgp.maintenance import cycle, evidence, knockout, patch, session

NESTED = (
    "MeanKsd_v1(MeanKsd_v1(CycleAffinity_v1(Ret_v1, LongWindow_60), LongWindow_60, KSigma_0p5),"
    " LongWindow_90, KSigma_0p5)"
)


def test_nested_knockout_uses_the_outer_nodes_own_true_output(arm3_lib, fit_box):
    """Finding 4: the outer node's median came from an output whose child was knocked out."""
    problem = problem_for(arm3_lib, fit_box)
    tree = deap_gp.PrimitiveTree.from_string(NESTED, arm3_lib.pset)
    ev = problem.evaluators["AAA"]
    d = problem.data["AAA"]
    ko = knockout.KnockoutEvaluator(ev, "MeanKsd_v1", (d.active_from, d.stop))
    true = ev(tree)[d.active_from : d.stop]
    value = ko(tree)
    finite = value[np.isfinite(value)]
    assert finite.size
    assert np.all(finite == np.median(true[np.isfinite(true)]))


def test_two_contracts_with_one_gp_node_name_are_refused():
    """Finding 3: ``build`` silently kept one implementation of two equal node names."""
    specs = libraries.resolve("arm3")
    op = next(s for s in specs if getattr(s, "domain", "") not in ("core", "data"))
    with pytest.raises(ValueError, match="GP node name"):
        build([*specs, op])


@pytest.mark.parametrize("name", ["dfa__exponent", "mean_ksd", "pruned_before"])
def test_a_grow_may_not_collide_with_any_node_or_lineage_name(tmp_path, results, name):  # noqa: F811
    """Finding 3 (``toy_a`` vs ``toy__a``; core names) and finding 7 (lineage, not state meta)."""
    root, arm3 = results
    folder, initial, initial_sha = folder_with_library(tmp_path, arm3, root)
    grow(folder, name)
    p = patch.read_patch(
        folder, "4-grow", arm3, initial, initial_sha, {}, None, ("pruned_before",),
        tmp_path / "w", gates=False,
    )  # fmt: skip
    assert any("is, or was, in the library" in x for x in p.problems), p.problems


def test_two_grows_with_one_node_name_are_refused(tmp_path, results):  # noqa: F811
    root, arm3 = results
    folder, initial, initial_sha = folder_with_library(tmp_path, arm3, root)
    grow(folder, "toy_a")
    grow(folder, "toy__a")
    p = patch.read_patch(
        folder, "4-grow", arm3, initial, initial_sha, {}, None, (), tmp_path / "w", gates=False
    )
    assert any("same operator name (or node name)" in x for x in p.problems)


def test_unused_operators_rank_lowest_within_the_bottom_quarter():
    """Finding 6: the reviewer's 12-operator case gives the bottom three, not five."""
    rows = {f"u{i}@1": {"usage": 0.0, "contribution": None} for i in range(2)}
    rows |= {f"o{c}@1": {"usage": 0.1, "contribution": float(c)} for c in range(1, 11)}
    assert evidence.low_keys(rows) == {"u0@1", "u1@1", "o1@1"}


def _fake_run(completed: bool) -> dict:
    return {"completed": completed, "subtype": "success" if completed else "error"}


def test_an_interrupted_repair_turn_is_not_a_completed_session(tmp_path, monkeypatch):
    """Finding 8: a repair that never completed was recorded as a completed session."""
    calls = []

    def run_claude(cmd, folder, archive, tag, timeout):
        calls.append(tag)
        return _fake_run(tag == "stream")  # the first turn completes, the repair never does

    monkeypatch.setattr(session.wp2, "run_claude", run_claude)
    monkeypatch.setattr(session.wp2, "completed", lambda r: r["completed"])
    monkeypatch.setattr(session.wp2, "limited", lambda r: False)
    monkeypatch.setattr(session.wp2, "copy_transcript", lambda *a: None)
    monkeypatch.setattr(session.time, "sleep", lambda s: None)
    record = session.run(
        "5", tmp_path / "archive", "brief", lambda f: None,
        lambda f: {"rules": [["a", "b"]], "problems": ["x"]}, lambda r: "fix it",
        root=tmp_path / "work",
    )  # fmt: skip
    assert calls[0] == "stream"
    assert "repair" in calls
    assert record["completed"] is False
    assert record["result"] is None
    again = session.run(  # resuming does not turn it into a completed session either
        "5", tmp_path / "archive", "brief", lambda f: None,
        lambda f: {"rules": [], "problems": []}, lambda r: None, root=tmp_path / "work",
    )  # fmt: skip
    assert again["completed"] is False


def test_describe_needs_a_passing_check_of_the_same_file(tmp_path):
    """Finding 5: describe ran unchecked drafts (e.g. an identity on log prices) on real data."""
    server = mcp_tools.AuthoringServer.__new__(mcp_tools.AuthoringServer)
    server.session, server.archive = tmp_path, tmp_path / "archive"
    server.archive.mkdir()
    server.limits, server.used = {"check": 5, "describe": 5}, {"check": 0, "describe": 0}
    server.lock = threading.Lock()
    (tmp_path / "draft.py").write_text("OPERATOR = 1\n")
    out = server.call("describe", {"file": "draft.py"})
    assert not out["ok"]
    assert "passed check" in out["error"]
    assert server.used["describe"] == 0
    sha = mcp_tools._sha(tmp_path / "draft.py")
    entry = {"tool": "check", "sha256": sha, "result": {"passed": True}}
    (server.archive / "evaluations.jsonl").write_text(json.dumps(entry) + "\n")
    assert sha in server._passed()
    (tmp_path / "draft.py").write_text("OPERATOR = 2\n")  # changed since: refused again
    assert not server.call("describe", {"file": "draft.py"})["ok"]


def test_errors_on_development_data_do_not_quote_values():
    """Finding 1: an exception message could carry data values back to the session."""
    value = 123.456789  # a data value: it reaches the message, never the operator's source
    try:
        raise ValueError(f"bad value {value} in window")
    except ValueError as exc:
        text = gates.withheld(exc)
    assert "123.456789" not in text
    assert text.startswith("ValueError raised on development data (message withheld)")


def test_rank_correlation_handles_ties():
    """Finding 9: ranks by position made constants correlate 1 and binary series spuriously."""
    assert worker._spearman(np.ones(100), np.ones(100)) is None
    a = np.array([0, 1] * 50, dtype=float)
    b = np.array([0, 0, 1, 1] * 25, dtype=float)
    assert worker._spearman(a, b) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.realdata
def test_a_campaign_resumes_only_under_its_own_specification():
    """Finding 2: a resumed campaign reused runs made under another GP budget."""
    import shutil

    from lpstgp.config import load_paths

    root = load_paths().results_dir / "wp3" / "maintenance" / "pytest-spec"
    shutil.rmtree(root, ignore_errors=True)
    try:
        kw = {"instruments": ("SPX",), "runs": 1, "cycles": 1, "workers": 1}
        first = cycle.Cycle("pytest-spec", ("PL1",), gp_overrides={"population": 20}, **kw)
        assert (root / "campaign.json").exists()
        cycle.Cycle("pytest-spec", ("PL1",), gp_overrides={"population": 20}, **kw)  # same: ok
        with pytest.raises(cycle.CampaignMismatchError, match="gp"):
            cycle.Cycle("pytest-spec", ("PL1",), gp_overrides={"population": 250}, **kw)
        task = first.tasks("PL1", cycle.ArmState("x"))[0]
        assert dict(task.campaign)["spec_digest"] == first.spec_digest
        fake = {"spec_digest": "other"}
        with pytest.raises(cycle.CampaignMismatchError):
            first._checked(fake, root / "cycle.json")
    finally:
        shutil.rmtree(root, ignore_errors=True)
