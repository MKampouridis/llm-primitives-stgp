"""Strategy contract, source policy, behavioural gates and the sandboxed worker."""

import textwrap
from pathlib import Path

import numpy as np
import pytest

from lpstgp.strategies import api, execute, gates
from lpstgp.strategies.loader import StrategyLoadError, load_file
from lpstgp.strategies.policy import check_strategy_source

FIXTURES = Path(__file__).parent / "fixtures"
TOY = FIXTURES / "toy_trend.py"

HEADER = "import numpy as np\nfrom strategy_api import Signal, Strategy, Window, rolling_mean\n"
FOOTER = """
STRATEGY = Strategy(
    name="bad", domain="spectral", hypothesis="h", definition="d", references=("r",),
    signals=(Signal("x", x, ("log_return",), {"window": Window(20)}, lambda window: LB),),
    rule=rule, rule_lookback=0,
)
"""
RULE = "def rule(s):\n    return np.where(s['x'] > 0, 1.0, 0.0), np.where(s['x'] < 0, 1.0, 0.0)\n"


def _write(tmp_path: Path, body: str, lookback: str = "window", rule: str = RULE) -> Path:
    path = tmp_path / "strategy.py"
    path.write_text(HEADER + textwrap.dedent(body) + rule + FOOTER.replace("LB", lookback))
    return path


def _failed(results):
    return {r["check"].split(" ")[0] for r in results if not r["passed"]}


@pytest.mark.parametrize(
    ("snippet", "message"),
    [
        ("import os\n", "import os"),
        ("from numpy import random\n", "from numpy import"),
        ("import numpy.random\n", "import numpy.random"),
        ("x = open('f')\n", "open"),
        ("y = getattr(np, 'load')\n", "getattr"),
        ("z = np.load('f')\n", ".load"),
        ("w = (1).__class__\n", ".__class__"),
        ("from scipy.stats import norm\nv = norm.rvs(size=3)\n", ".rvs"),
        ("def f():\n    global G\n", "global"),
        ("import socket\n", "import socket"),
    ],
)
def test_source_policy_rejects(snippet, message):
    problems = check_strategy_source(HEADER + snippet + "STRATEGY = None\n")
    assert any(message in p for p in problems), problems


def test_source_policy_accepts_the_toy_and_requires_strategy():
    assert check_strategy_source(TOY.read_text()) == []
    assert any("STRATEGY" in p for p in check_strategy_source("import numpy as np\n"))


def test_contract_validates_structure():
    with pytest.raises(ValueError, match="grid"):
        api.Window(25)
    with pytest.raises(ValueError, match="keyword-only"):
        api.Signal(
            "s",
            lambda x, window: x,
            ("log_return",),
            {"window": api.Window(20)},
            lambda window: window,
        )
    with pytest.raises(ValueError, match="inputs"):
        api.Signal(
            "s",
            lambda x, *, window: x,
            ("close",),
            {"window": api.Window(20)},
            lambda window: window,
        )


def test_param_grids_match_the_gp_types():
    from lpstgp import types

    for name, kind in api.KINDS.items():
        assert kind.grid == getattr(types, name).grid, name


def test_toy_strategy_passes_behavioural_gates():
    strategy = load_file(TOY)
    results = gates.behaviour(strategy)
    assert gates.passed(results), [r for r in results if not r["passed"]]
    assert strategy.lookback == 60 + 119  # longest default signal + rule


@pytest.mark.parametrize(
    ("body", "lookback", "failing"),
    [
        # look-ahead: uses tomorrow's return
        (
            "def x(log_return, *, window):\n    return np.roll(rolling_mean(log_return, window), -1)\n",
            "window",
            "prefix-invariant",
        ),
        # declared lookback too short
        (
            "def x(log_return, *, window):\n    return rolling_mean(log_return, 2 * window)\n",
            "window",
            "lookback",
        ),
        # unbounded memory (cumulative sum)
        (
            "def x(log_return, *, window):\n    return np.nancumsum(log_return)\n",
            "window",
            "lookback",
        ),
        # wrong length
        (
            "def x(log_return, *, window):\n    return rolling_mean(log_return, window)[1:]\n",
            "window",
            "type",
        ),
    ],
)
def test_gates_catch_bad_signals(tmp_path, body, lookback, failing):
    strategy = load_file(_write(tmp_path, body, lookback))
    assert failing in _failed(gates.behaviour(strategy))


def test_gates_catch_a_stateful_rule(tmp_path):
    rule = "CALLS = [0]\ndef rule(s):\n    CALLS[0] += 1\n    e = np.full(len(s['x']), float(CALLS[0] % 2))\n    return e, 1.0 - e\n"
    body = "def x(log_return, *, window):\n    return rolling_mean(log_return, window)\n"
    strategy = load_file(_write(tmp_path, body, rule=rule))
    assert "strategy" in _failed(gates.behaviour(strategy))


def test_gates_on_development_data_flag_a_never_trading_rule(tmp_path):
    rule = "def rule(s):\n    z = np.zeros(len(s['x']))\n    return z, z\n"
    body = "def x(log_return, *, window):\n    return rolling_mean(log_return, window)\n"
    strategy = load_file(_write(tmp_path, body, rule=rule))
    lp, lr = gates.synthetic_inputs()
    results = gates.on_development_data(strategy, {"A": (lp, lr, 200), "B": (lp, lr, 200)})
    assert not gates.passed(results)


def test_loader_reports_policy_and_runtime_errors(tmp_path):
    bad = tmp_path / "s.py"
    bad.write_text("import os\nSTRATEGY = 1\n")
    with pytest.raises(StrategyLoadError, match="import os"):
        load_file(bad)
    bad.write_text("import numpy as np\nSTRATEGY = 1 / 0\n")
    with pytest.raises(StrategyLoadError, match="ZeroDivisionError"):
        load_file(bad)


def test_worker_runs_sandboxed_and_is_deterministic_across_processes(tmp_path):
    described = execute.run("describe", TOY, tmp_path / "job1")
    assert described["ok"], described
    assert [s["name"] for s in described["strategy"]["signals"]] == ["trend", "volatility", "gap"]
    one = execute.run("hash", TOY, tmp_path / "job2", threads=1)
    four = execute.run("hash", TOY, tmp_path / "job3", threads=4)
    assert one["ok"]
    assert one["hash"] == four["hash"]
    lp, lr = gates.synthetic_inputs()
    inputs = tmp_path / "inputs.npz"
    np.savez(inputs, **{"lp::A": lp, "lr::A": lr, "start::A": np.int64(200)})
    evaluated = execute.run("evaluate", TOY, tmp_path / "job4", inputs_path=inputs)
    assert set(evaluated["arrays"]) >= {"entry::A", "exit::A", "signal::A::trend"}
    report = execute.run("gates", TOY, tmp_path / "job5", inputs_path=inputs)
    assert report["ok"]
    assert report["passed"], report


@pytest.mark.skipif(not execute.sandboxed(), reason="macOS sandbox-exec only")
def test_sandbox_profile_blocks_writes_outside_the_job_and_network(tmp_path):
    import subprocess
    import sys

    job = tmp_path / "job"
    job.mkdir()
    profile = execute.PROFILE.format(job=job.resolve())
    outside = tmp_path / "outside.txt"
    write = f"open({str(outside)!r}, 'w').write('x')"
    proc = subprocess.run(
        [execute.SANDBOX_EXEC, "-p", profile, sys.executable, "-c", write], capture_output=True
    )
    assert proc.returncode != 0
    assert not outside.exists()
    net = "import socket; socket.create_connection(('example.com', 80), timeout=5)"
    proc = subprocess.run(
        [execute.SANDBOX_EXEC, "-p", profile, sys.executable, "-c", net], capture_output=True
    )
    assert proc.returncode != 0


def test_worker_reports_failures_without_raising(tmp_path):
    body = "def x(log_return, *, window):\n    raise RuntimeError('boom')\n"
    path = _write(tmp_path, body)
    result = execute.run("gates", path, tmp_path / "job")
    assert result["ok"]
    assert not result["passed"]
    assert "runs" in _failed(result["results"])
    bad = tmp_path / "policy.py"
    bad.write_text("import os\nSTRATEGY = 1\n")
    assert execute.run("evaluate", bad, tmp_path / "job2")["stage"] == "load"
