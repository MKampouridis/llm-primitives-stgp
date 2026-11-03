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


def _fake_maintenance(tmp_path, campaign="m"):
    for arm, out in (
        ("4-grow", {"state_id": "aaaa", "seed_rules": []}),
        ("4-full", {"state_id": "bbbb", "seed_rules": []}),
        ("5", {"state_id": "cccc", "seed_rules": [["E1", "X1"], ["E2", "X2"]]}),
    ):
        d = tmp_path / "wp3" / "maintenance" / campaign / arm / "P03" / "c3"
        d.mkdir(parents=True)
        (d / "cycle.json").write_text(json.dumps({"state_out": out}))
    return SimpleNamespace(results_dir=tmp_path)


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
