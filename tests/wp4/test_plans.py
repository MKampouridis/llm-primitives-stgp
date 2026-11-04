"""WP4 reported-run configurations (protocol_wp4 §3-4): every arm, and the maintained arms'
period libraries and seeds taken from the M3 campaign's last cycle."""

import json
import sys
from types import SimpleNamespace

from lpstgp.campaign.plan import Config
from lpstgp.config import REPO_ROOT, load_settings

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import wp4

SETTINGS = load_settings()


def fake_cycle_end(root, arm, period, out, cycles=3):
    """A maintenance campaign's last cycle and lineage, as M3 writes them (spec-checked)."""
    from lpstgp.freeze import digest
    from lpstgp.maintenance.cycle import ArmState

    spec_path = root / "campaign.json"
    if not spec_path.exists():
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps({"campaign": root.name}))
    spec = json.loads(spec_path.read_text())
    # stands in for M3's design specification, in whichever copy of the script is loaded
    for module in {wp4, sys.modules.get("wp4")} - {None}:
        module._SPECS[root.name] = spec
    d = root / arm / period / f"c{cycles}"
    d.mkdir(parents=True)
    (d / "cycle.json").write_text(json.dumps({"state_out": out, "spec_digest": digest(spec)}))
    row = {"cycle": cycles, "state_out": out["state_id"],
           "rules_out": ArmState.from_dict(out).batch_key}  # fmt: skip
    (root / arm / period / "lineage.json").write_text(json.dumps({"cycles": [row]}))


def _fake_maintenance(tmp_path, campaign="m"):
    root = tmp_path / "wp3" / "maintenance" / campaign
    for arm, out in (
        ("4-grow", {"state_id": "aaaa", "seed_rules": []}),
        ("4-full", {"state_id": "bbbb", "seed_rules": []}),
        ("5", {"state_id": "cccc", "seed_rules": [["E1", "X1"], ["E2", "X2"]]}),
    ):
        fake_cycle_end(root, arm, "P03", out)
    return SimpleNamespace(results_dir=tmp_path)


def test_a_last_cycle_that_disagrees_with_its_lineage_or_specification_is_refused(tmp_path):
    import pytest

    paths = _fake_maintenance(tmp_path)
    root = tmp_path / "wp3" / "maintenance" / "m"
    lineage = root / "4-full" / "P03" / "lineage.json"
    good = lineage.read_text()
    lineage.write_text(good.replace("bbbb", "dddd"))
    with pytest.raises(SystemExit, match="lineage"):
        wp4.maintained_state(paths, "m", "4-full", "P03")
    lineage.write_text(good)
    (root / "campaign.json").write_text(json.dumps({"campaign": "other"}))
    with pytest.raises(SystemExit, match="specification"):
        wp4.maintained_state(paths, "m", "4-full", "P03")


def test_every_arm_of_the_protocol_is_configured(tmp_path):
    paths = _fake_maintenance(tmp_path)
    configs = {c.name: c for c in wp4.wp4_configs(paths, SETTINGS, "P03", "m")}
    assert set(configs) == {
        "arm1", "arm2a", "arm2b", "arm2c", "arm3", "arm6", "armGPconv", "armTA",
        "arm4grow", "arm4full", "arm5",
    }  # fmt: skip
    assert configs["arm4grow"].library == "state:aaaa"
    assert configs["arm4full"].library == "state:bbbb"
    assert configs["arm5"].library == "arm3"
    assert configs["arm5"].seed_rules == (("E1", "X1"), ("E2", "X2"))
    assert configs["armGPconv"].library == "conventional"
    gp = {c.name: c.gp for c in configs.values() if c.kind == "gp"}
    assert len({json.dumps(g, sort_keys=True) for g in gp.values()}) == 1  # one budget for all


def test_seed_rules_and_authored_libraries_enter_the_configuration_digest():
    plain = Config("a", "arm3", gp={"population": 250})
    seeded = Config("a", "arm3", gp={"population": 250}, seed_rules=(("E", "X"),))
    assert plain.digest(SETTINGS) != seeded.digest(SETTINGS)
    # an earlier configuration (WP2's arm 2c) keeps its registered digest
    wp2 = Config("arm2c", "s2c", gp={"population": 250, "generations": 70, "tournament": 5})
    registered = [
        r.split(",")[5]
        for r in (REPO_ROOT / "reports" / "configuration_register.csv").read_text().splitlines()
        if r.split(",")[1:3] == ["wp2-gonogo-PL1", "arm2c"]
    ]
    assert wp2.digest(SETTINGS) == registered[0]


def test_a_maintenance_campaign_under_another_design_is_refused(tmp_path):
    """D-088 (ChatGPT): a self-consistent campaign with stale digests or runs=1 is not M3."""
    import pytest

    paths = _fake_maintenance(tmp_path, campaign="stale")
    wp4._SPECS["stale"] = {"campaign": "stale", "runs": 3}  # what M3 would be now
    with pytest.raises(SystemExit, match="not WP4's M3 design"):
        wp4.maintained_state(paths, "stale", "4-full", "P03")


def test_the_expected_maintenance_specification_is_maintain_py_wp4s(tmp_path, monkeypatch):
    """Runs on a clean checkout (no ``config/paths.toml``, no data): temporary paths (D-089)."""
    from lpstgp.config import load_paths
    from lpstgp.maintenance import cycle

    paths_file = tmp_path / "paths.toml"
    paths_file.write_text(
        f'data_dir = "{tmp_path / "data"}"\nresults_dir = "{tmp_path / "results"}"\n'
        f'reports_dir = "{tmp_path / "reports"}"\ncache_dir = "{tmp_path / "cache"}"\n'
    )
    monkeypatch.setenv("LPSTGP_PATHS", str(paths_file))
    spec = wp4.expected_maintenance_spec("pytest-never-written")
    assert [p["id"] for p in spec["periods"]] == [*(f"P{k:02d}" for k in range(1, 19)), "PC"]
    assert spec["runs"] == cycle.RUNS_PER_INSTRUMENT
    assert spec["cycles"] == cycle.CYCLES
    table = json.loads((REPO_ROOT / "reports" / "wp4" / "eligibility.json").read_text())
    assert spec["instruments"] == table["eligible"]
    assert not (load_paths().results_dir / "wp3" / "maintenance" / "pytest-never-written").exists()
    wp4._SPECS.pop("pytest-never-written")  # built under temporary paths: not for other tests


def test_design_tasks_cover_every_instrument_run_and_seed(tmp_path):
    paths = _fake_maintenance(tmp_path)
    tasks = wp4.design_tasks(paths, SETTINGS, "P03", "m")
    table = json.loads((REPO_ROOT / "reports" / "wp4" / "eligibility.json").read_text())
    n = len(table["eligible"]["P03"])
    assert len(tasks) == n * (1 + 10 * wp4.RUNS)  # arm 1 once, ten GP arms x 50 runs
    assert len({t["id"] for t in tasks}) == len(tasks)
    seeds = {(tuple(t["instruments"]), t["run"]): t["seed"] for t in tasks}
    assert all(seeds[(tuple(t["instruments"]), t["run"])] == t["seed"] for t in tasks)  # paired
