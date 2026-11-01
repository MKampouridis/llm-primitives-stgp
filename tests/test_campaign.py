"""Campaign plans, paired seeds, resumable execution, collection and the configuration register."""

import csv
from pathlib import Path

import pytest
from tests.gp.conftest import write_synthetic_tier

from lpstgp.campaign.collect import collect
from lpstgp.campaign.execute import (
    PlanMismatchError,
    execute_plan,
    execute_slice,
    load_plan,
    progress,
    verify,
)
from lpstgp.campaign.plan import Config, register_configs, run_seed, write_plan
from lpstgp.config import load_paths, load_settings

TINY = {"population": 8, "generations": 1, "elitism": 1, "hof_size": 2, "cache_mb": 32}


def test_seeds_pair_arms_and_differ_across_runs():
    assert run_seed(("SPX",), "PL1", 1) == run_seed(("SPX",), "PL1", 1)
    assert run_seed(("SPX",), "PL1", 1) != run_seed(("SPX",), "PL1", 2)
    assert run_seed(("SPX",), "PL1", 1) != run_seed(("NDX",), "PL1", 1)
    assert 0 <= run_seed(("SPX",), "PL2", 30) < 2**32


@pytest.fixture
def campaign_paths(tmp_path, monkeypatch):
    write_synthetic_tier(tmp_path / "data" / "tierA")
    paths_file = tmp_path / "paths.toml"
    paths_file.write_text(
        f'data_dir = "{tmp_path / "data"}"\nresults_dir = "{tmp_path / "results"}"\n'
        f'reports_dir = "{tmp_path / "reports"}"\ncache_dir = "{tmp_path / "cache"}"\n'
    )
    monkeypatch.setenv("LPSTGP_PATHS", str(paths_file))  # inherited by spawned workers
    return load_paths()


@pytest.mark.slow
def test_plan_execute_resume_collect(campaign_paths, tmp_path):
    settings = load_settings()
    gp = {k: v for k, v in TINY.items() if k != "cache_mb"} | {"cache_bytes": 32 * 2**20}
    configs = [Config("arm_a", "seed", gp=gp), Config("arm_b", "technical", gp=gp)]
    register = tmp_path / "register.csv"
    plan_path = write_plan(
        "unit", configs, [(("AAA",), "PL1")], 2, campaign_paths, settings, register=register
    )
    plan = load_plan(plan_path)
    assert len(plan["tasks"]) == 4
    seeds = {(t["config"], t["run"]): t["seed"] for t in plan["tasks"]}
    assert seeds["arm_a", 1] == seeds["arm_b", 1]  # paired across arms
    counts = execute_plan(plan_path, campaign_paths, settings, workers=2)
    assert counts == {"skipped": 0, "selected": 0, "evolved": 4}
    assert execute_plan(plan_path, campaign_paths, settings, workers=2)["skipped"] == 4
    first = sorted(plan_path.parent.glob("tier*/*/*.json"))[0]
    (first.parent / "stray_copy.json").write_text(first.read_text())  # a duplicate on disk
    table = collect(plan_path)
    assert len(table) == 4  # only the plan's tasks, each once
    assert set(table["config"]) == {"arm_a", "arm_b"}
    assert (plan_path.parent / "runs.parquet").exists()
    changed = {**settings, "fitness": {**settings["fitness"], "lambda_size": 0.02}}
    assert verify(plan, campaign_paths, changed)
    with pytest.raises(PlanMismatchError):
        execute_plan(plan_path, campaign_paths, changed)
    with register.open() as handle:
        assert [row["config"] for row in csv.DictReader(handle)] == ["arm_a", "arm_b"]


def test_register_appends_each_configuration_once(tmp_path):
    register = tmp_path / "r.csv"
    register_configs(register, "c1", {"x": {"library": "s2c", "kind": "gp", "digest": "d1"}})
    register_configs(register, "c2", {"x": {"library": "s2c", "kind": "gp", "digest": "d1"}})
    register_configs(register, "c2", {"x": {"library": "s2c", "kind": "gp", "digest": "d2"}})
    with Path(register).open() as handle:
        rows = list(csv.DictReader(handle))
    assert [(r["campaign"], r["digest"]) for r in rows] == [("c1", "d1"), ("c2", "d2")]


@pytest.mark.slow
def test_slices_match_pooled_execution(campaign_paths, tmp_path):
    """Cluster slices (in-process) give the same records as the process pool, and resume."""
    import json
    import shutil

    settings = load_settings()
    gp = {k: v for k, v in TINY.items() if k != "cache_mb"} | {"cache_bytes": 32 * 2**20}
    configs = [Config("arm_a", "seed", gp=gp), Config("arm_b", "technical", gp=gp)]
    plan_path = write_plan(
        "slices", configs, [(("AAA",), "PL1")], 2, campaign_paths, settings, register=None
    )
    assert progress(plan_path, settings) == {"tasks": 4, "complete": 0}
    assert execute_slice(plan_path, campaign_paths, settings, 0, 3)["evolved"] == 3
    assert execute_slice(plan_path, campaign_paths, settings, 2, 2) == {
        "skipped": 1, "selected": 0, "evolved": 1,
    }  # fmt: skip
    assert progress(plan_path, settings)["complete"] == 4
    with pytest.raises(IndexError):
        execute_slice(plan_path, campaign_paths, settings, 4)
    sliced = {p.name: json.loads(p.read_text()) for p in plan_path.parent.glob("tier*/*/*.json")}
    pooled_dir = tmp_path / "pooled"
    pooled_dir.mkdir()
    shutil.copy(plan_path, pooled_dir / "tasks.json")
    execute_plan(pooled_dir / "tasks.json", campaign_paths, settings, workers=2)
    pooled = {p.name: json.loads(p.read_text()) for p in pooled_dir.glob("tier*/*/*.json")}
    assert sliced.keys() == pooled.keys()
    assert len(sliced) == 4
    for name, record in sliced.items():
        assert record["hall_of_fame"] == pooled[name]["hall_of_fame"]


@pytest.mark.slow
def test_one_failing_run_does_not_stop_the_others(campaign_paths, tmp_path):
    from lpstgp.runner import RunFailuresError, RunTask, configs_from_settings, run_many

    settings = load_settings()
    gp, fitness = configs_from_settings(
        settings, **{k: v for k, v in TINY.items() if k != "cache_mb"}
    )
    good = RunTask("unit", "seed", ("AAA",), "PL1", 1, gp, fitness)
    bad = RunTask("unit", "no-such-library", ("AAA",), "PL1", 1, gp, fitness)
    with pytest.raises(RunFailuresError, match="no-such-library"):
        run_many([bad, good], 2, tmp_path / "out")
    assert (tmp_path / "out" / "tierA" / "unit" / f"{good.name}.json").exists()


def test_code_change_or_empty_result_never_counts_as_complete(campaign_paths, monkeypatch):
    import json

    from lpstgp.campaign import execute
    from lpstgp.runner import record_path

    settings = load_settings()
    gp = {k: v for k, v in TINY.items() if k != "cache_mb"} | {"cache_bytes": 32 * 2**20}
    plan_path = write_plan(
        "code", [Config("arm_a", "seed", gp=gp)], [(("AAA",), "PL1")], 1, campaign_paths,
        settings, register=None,
    )  # fmt: skip
    plan = load_plan(plan_path)
    assert plan["source_digest"]
    assert not verify(plan, campaign_paths, settings)
    monkeypatch.setattr(execute, "source_digest", lambda: "edited")
    assert any("source code" in p for p in verify(plan, campaign_paths, settings))
    monkeypatch.undo()
    run = execute.run_task(plan, plan["tasks"][0], settings)
    path = record_path(plan_path.parent, run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"campaign": dict(run.campaign), "hall_of_fame": [], "selected": 0}))
    assert not execute.is_complete(path, run)  # an empty result is not a finished run


def test_identical_replan_is_untouched_and_a_changed_plan_cannot_replace_records(
    campaign_paths,
):
    from lpstgp.campaign.execute import IncompleteCampaignError, plan_records
    from lpstgp.campaign.plan import PlanExistsError

    settings = load_settings()
    gp = {k: v for k, v in TINY.items() if k != "cache_mb"} | {"cache_bytes": 32 * 2**20}
    configs = [Config("arm_a", "seed", gp=gp)]
    cells = [(("AAA",), "PL1")]
    plan_path = write_plan("same", configs, cells, 2, campaign_paths, settings, register=None)
    before = plan_path.read_text()
    assert write_plan("same", configs, cells, 2, campaign_paths, settings, register=None)
    assert plan_path.read_text() == before  # created_utc included: the file is untouched
    execute_plan(plan_path, campaign_paths, settings, workers=1)
    assert len(plan_records(plan_path, campaign_paths, settings)) == 2
    with pytest.raises(PlanExistsError):  # 3 runs instead of 2, with records present
        write_plan("same", configs, cells, 3, campaign_paths, settings, register=None)
    sorted(plan_path.parent.glob("tier*/*/*.json"))[0].unlink()
    with pytest.raises(IncompleteCampaignError):
        plan_records(plan_path, campaign_paths, settings)
    with pytest.raises(IncompleteCampaignError):
        collect(plan_path, campaign_paths, settings)


def test_source_digest_follows_real_source_edits(tmp_path):
    from lpstgp.campaign.plan import source_digest

    root = tmp_path / "pkg"
    (root / "sub").mkdir(parents=True)
    (root / "a.py").write_text("x = 1\n")
    (root / "sub" / "b.py").write_text("y = 2\n")
    first = source_digest(root)
    assert source_digest(root) == first
    (root / "sub" / "b.py").write_text("y = 3\n")
    assert source_digest(root) != first
    (root / "sub" / "b.py").write_text("y = 2\n")
    assert source_digest(root) == first
    (root / "c.py").write_text("")  # a new module counts too
    assert source_digest(root) != first
