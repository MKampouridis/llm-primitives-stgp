"""Regression tests for the WP3 code review's findings (D-074); each reproduces the reported case."""

import json
import threading
from pathlib import Path

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


# --- the follow-up review (D-081) -------------------------------------------------------------


def test_contract_imports_are_limited_to_the_contracts_own_names():
    """Follow-up finding 1: ``from operator_api import inspect`` reached the builtins."""
    from lpstgp.strategies.policy import check_llm_source

    attacks = [
        "from operator_api import Operator, inspect\nOPERATOR = 1\n",
        "from operator_api import np\nOPERATOR = 1\n",
        "import operator_api\nOPERATOR = 1\n",
        "import numpy as np\nf = np.linalg.norm\nx = f.__call__\nOPERATOR = 1\n",
        "from operator_api import Operator\nx = Operator.__init__\nOPERATOR = 1\n",
        "import scipy.stats as st\nx = st.norm.cdf.f_globals\nOPERATOR = 1\n",
        "import numpy as np\nx = np.sys.argv\nOPERATOR = 1\n",
        "import numpy as np\nx = np.os.environ\nOPERATOR = 1\n",
    ]
    for source in attacks:
        assert check_llm_source(source, "operator_api", "OPERATOR", "Operator"), source
    ok = "from operator_api import Operator, Real, Series, trailing_windows\nOPERATOR = 1\n"
    assert not check_llm_source(ok, "operator_api", "OPERATOR", "Operator")


def test_a_result_the_worker_did_not_sign_is_refused(tmp_path, monkeypatch):
    """Follow-up finding 1: an operator wrote its own passing ``gates.json`` and exited."""
    import subprocess

    from lpstgp.strategies import execute

    def forged(cmd, **kwargs):
        out = __import__("pathlib").Path(cmd[cmd.index("-") + 1])
        out.write_text(json.dumps({"ok": True, "passed": True, "results": []}))
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(execute.subprocess, "run", forged)
    (tmp_path / "op.py").write_text("OPERATOR = 1\n")
    result = execute.run("gates", tmp_path / "op.py", tmp_path / "job")
    assert result == {"ok": False, "stage": "integrity", "error": "the result was not the worker's"}


def test_the_channel_signs_and_verifies(tmp_path):
    from lpstgp.strategies import channel

    secret = channel.new_secret()
    path = tmp_path / "r.json"
    channel.write_signed(path, b'{"ok": true}', secret)
    assert channel.read_verified(path, secret) == b'{"ok": true}'
    assert channel.read_verified(path, channel.new_secret()) is None
    path.write_bytes(b'{"ok": true, "passed": true}')  # changed after signing
    assert channel.read_verified(path, secret) is None
    arrays = tmp_path / "in.npz"
    np.savez(arrays, **{"lp::I01": np.ones(3), "lr::I01": np.zeros(3), "start::I01": np.int64(1)})
    got_secret, inputs = channel.receive(__import__("io").BytesIO(channel.message(secret, arrays)))
    assert got_secret == secret
    assert inputs["I01"][2] == 1


def test_the_campaign_specification_keeps_the_period_order():
    """Follow-up finding 2: swapping the periods left the specification's digest unchanged."""
    loop = cycle.Cycle.__new__(cycle.Cycle)
    with pytest.raises(ValueError, match="chronological"):
        loop._check_periods(("PL2", "PL1"))
    with pytest.raises(ValueError, match="twice"):
        loop._check_periods(("PL1", "PL1"))
    loop._check_periods(("PL1", "PL2"))


def test_the_source_digest_covers_prompts_and_other_resources(tmp_path):
    """Follow-up finding 3: a prompt change did not change the source digest."""
    from lpstgp.campaign.plan import source_digest

    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "prompts").mkdir()
    prompt = tmp_path / "prompts" / "brief.md"
    prompt.write_text("Do this.")
    before = source_digest(tmp_path)
    prompt.write_text("Do that.")
    assert source_digest(tmp_path) != before
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"junk")
    assert source_digest(tmp_path) == source_digest(tmp_path)


# --- ChatGPT's review of the WP4 M1 code (D-088) -------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "from numpy import __builtins__ as b",
        "from scipy.stats import _stats_py",
        "from scipy.special import inspect",
        "from numpy import os",
        "from numpy.linalg import norm",
        "from math import sqrt as __s",
        "import numpy as _np",
        "from scipy.stats import no_such_name",
        "from typing import *",
    ],
)
def test_from_imports_are_an_allowlist_of_public_names(line):
    from lpstgp.strategies.policy import check_llm_source

    assert check_llm_source(f"{line}\nOPERATOR = 1\n", "operator_api", "OPERATOR", "Operator")


def test_ordinary_imports_still_pass():
    from lpstgp.strategies.policy import check_llm_source

    ok = (
        "from __future__ import annotations\nimport math\nimport numpy as np\n"
        "from numpy import linalg\nfrom scipy.stats import norm, rankdata\n"
        "from typing import Any\nfrom collections.abc import Sequence\nOPERATOR = 1\n"
    )
    assert check_llm_source(ok, "operator_api", "OPERATOR", "Operator") == []


def test_a_slim_record_keeps_the_rule_and_little_else():
    from lpstgp import pilot

    gp = {
        "campaign": {"task_id": "t", "config": "arm3", "run": "1"}, "instruments": ["SPX"],
        "library": {"name": "arm3", "lock": "x"}, "selected": 1,
        "hall_of_fame": [{"entry": "a", "exit": "b"}, {"entry": "c", "exit": "d", "f": 1}],
        "generations": [{"best": 0.1}] * 70,
    }  # fmt: skip
    small = pilot.slim(gp)
    assert pilot.rule_hash(small) == pilot.rule_hash(gp)
    assert "generations" not in small
    select = {
        "campaign": {"task_id": "s"}, "instruments": ["SPX"], "kind": "select",
        "library": {"strategies_lock": "L"}, "selection": {"SPX": {"selected": "s01", "f": 2}},
    }  # fmt: skip
    assert pilot.rule_hash(pilot.slim(select)) == pilot.rule_hash(select)


# --- ChatGPT's re-check of D-088 (D-089) ---------------------------------------------------

PROBE = (
    "\nclass Probe:\n    value: \"__import__('builtins').open\"\n\n"
    "reader = {call}(Probe)['value']\n"
)


@pytest.mark.parametrize(
    ("imports", "call"),
    [
        ("from typing import get_type_hints", "get_type_hints"),
        ("import typing", "typing.get_type_hints"),
        ("import typing as t", "t.get_type_hints"),
        ("from typing import ForwardRef", "ForwardRef"),
        ("import collections.abc", "collections.namedtuple"),
        ("import scipy.stats", "scipy.LowLevelCallable"),
    ],
)
def test_string_evaluation_is_refused_in_frozen_modules(imports, call):
    """ChatGPT's probe appended to a real frozen strategy and a real frozen operator."""
    from lpstgp.authoring.loader import check_source
    from lpstgp.strategies.policy import check_strategy_source

    root = Path(__file__).resolve().parents[2] / "src" / "lpstgp"
    strategy = (root / "strategies" / "generated" / "fractal" / "s17__v1.py").read_text()
    operator = root / "authoring" / "generated" / "arm3" / "fractal" / "dfa_exponent__v1.py"
    probe = f"{imports}\n{PROBE.format(call=call)}"
    assert check_strategy_source(strategy) == []
    assert check_source(operator.read_text()) == []
    assert check_strategy_source(strategy + probe)
    assert check_source(operator.read_text() + probe)


def test_typing_and_collections_abc_give_only_their_listed_names():
    from lpstgp.strategies.policy import check_llm_source

    def check(body):
        return check_llm_source(f"{body}\nOPERATOR = 1\n", "operator_api", "OPERATOR", "Operator")

    assert check("from typing import Any, Optional\nimport typing\nx: typing.Sequence = ()") == []
    assert check("import collections.abc as c\nx: c.Mapping = {}\nimport scipy.stats") == []
    assert check("import scipy.stats\ny = scipy.stats.rankdata\nz = scipy.special.ndtr") == []
    assert check("from typing import cast")
    assert check("import typing\nx = typing.TYPE_CHECKING")
    assert check("from collections.abc import sys")


@pytest.mark.slow
def test_nothing_reaches_the_interpreter_through_the_allowed_libraries():
    """Every attribute path the policy admits, three levels deep from each allowed library
    and each listed typing name, avoids builtins that open files or evaluate strings, the
    import machinery and the process modules (D-088, D-089)."""
    import builtins
    import importlib
    import inspect
    import io
    import os
    import types
    import typing
    import warnings

    from lpstgp.strategies import policy

    banned = {getattr(builtins, n) for n in sorted(policy.FORBIDDEN_NAMES - {"__builtins__"})}
    banned |= {typing.get_type_hints, typing.ForwardRef, importlib.import_module,
               inspect.currentframe, io.open, os.system, os.popen}  # fmt: skip
    banned_ids = {id(b) for b in banned}
    modules = {"os", "sys", "subprocess", "builtins", "importlib", "inspect", "io", "pathlib",
               "ctypes", "pickle", "socket", "shutil", "typing", "runpy", "code", "pydoc",
               "tempfile", "threading", "multiprocessing", "signal"}  # fmt: skip
    hits, seen = [], set()

    def walk(obj, path, depth):
        if id(obj) in banned_ids:
            hits.append(path)
            return
        if isinstance(obj, types.ModuleType) and obj.__name__.split(".")[0] in modules:
            hits.append(f"{path} -> {obj.__name__}")
            return
        if depth == 0 or id(obj) in seen:
            return
        seen.add(id(obj))
        try:
            names = dir(obj)
        except Exception:
            return
        for name in names:
            if policy._bad_name(name):
                continue
            try:
                value = getattr(obj, name)
            except Exception:
                continue
            walk(value, f"{path}.{name}", depth - 1)

    roots = {m: importlib.import_module(m) for m in policy.COMMON_IMPORTS
             if m not in ("__future__", *policy.EXPLICIT_EXPORTS)}  # fmt: skip
    for module, names in policy.EXPLICIT_EXPORTS.items():
        for name in names:
            roots[f"{module}.{name}"] = getattr(importlib.import_module(module), name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for path, obj in roots.items():
            seen.clear()
            walk(obj, path, 3)
    assert not hits, hits[:20]
