"""GP development E1 (D-090): cells, configurations and the pre-registered pass marks."""

import sys

import numpy as np
import pytest

from lpstgp.config import REPO_ROOT, load_settings

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gp_dev


def _rows(gain, rho_sign, config="e1-2c-lcb", data="pooled", cells=12, runs=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(cells):
        fit = rng.normal(1, 0.3, runs)
        val = rho_sign * fit + rng.normal(0, 0.1, runs)
        for f, v in zip(fit, val, strict=True):
            rows.append({"config": config, "data": data, "cell": (str(c), "PL1"),
                         "fit_score": f, "fit_sharpe": f, "val_sharpe": v,
                         "val_gen0": 0.5, "val_last": 0.5 + gain + rng.normal(0, 0.02),
                         "trades_fit": 10, "exposure_fit": 0.5, "exposure_val": 0.5})  # fmt: skip
    return rows


def test_pass_marks_need_both_an_evolution_gain_and_predictive_training_scores():
    good = gp_dev.e1_summary(_rows(0.3, +1))["e1-2c-lcb/pooled"]
    assert good["passes"]
    no_gain = gp_dev.e1_summary(_rows(0.0, +1))["e1-2c-lcb/pooled"]
    assert not no_gain["pass_gain"]
    assert not no_gain["passes"]
    unpredictive = gp_dev.e1_summary(_rows(0.3, -1))["e1-2c-lcb/pooled"]
    assert unpredictive["pass_gain"]
    assert not unpredictive["passes"]
    report = gp_dev.e1_report(gp_dev.e1_summary(_rows(0.3, +1)))
    assert "go to E2 with e1-2c-lcb/pooled" in report
    assert "stop and rethink" in gp_dev.e1_report(gp_dev.e1_summary(_rows(0.0, +1)))


def test_cells_use_only_validation_years_before_wp4s_first_test_year():
    from lpstgp.splits import all_periods

    periods = all_periods(load_settings())
    cells = gp_dev.e1_cells()
    assert {p for _, p in cells} == {"PL1", "PL2", "P01"}
    # the VALIDATE horizon is the test start: no read reaches 2008-07-01, P01's test year
    assert max(periods[p].test_start for _, p in cells).isoformat() == "2008-07-01"
    pooled = [i for i, _ in cells if len(i) > 1]
    assert len(pooled) == 10
    assert all(len(set(i)) == len(i) for i in pooled)
    names = [c.name for c in gp_dev.e1_configs(load_settings())]
    assert names == ["e1-2c-comp", "e1-2c-lcb", "e1-TA-comp", "e1-TA-lcb"]


def test_e2_configurations_and_the_benchmark_mark():
    configs = gp_dev.e2_configs(load_settings())
    assert [c.name for c in configs] == ["e2-2c", "e2-TA"]
    assert all(dict(c.fitness) == {"position_mode": "reverse", "vol_target": 0.10} for c in configs)
    rows = [{"config": "e2-2c", "cell": ("A+B", "G1"), "val_sharpe": v} for v in (0.9, 1.0, 1.1)]
    rows += [{"config": "e2-2c", "cell": ("C+D", "G3"), "val_sharpe": v} for v in (0.2, 0.3)]
    bench = {("A+B", "G1"): {"trend": 0.8, "hold": 1.2}, ("C+D", "G3"): {"trend": 0.5, "hold": 0.0}}
    got = gp_dev.e2_compare(rows, bench)["e2-2c"]
    assert got["vs_trend"] == pytest.approx(np.median([0.2, -0.25]))
    assert got["pass_benchmark"] is False  # -0.025 < 0


def test_the_gate_bar_is_the_expected_maximum_of_null_sharpe_ratios():
    rng = np.random.default_rng(0)
    n, bars = 500, 1500
    maxima = [max(rng.normal(0, 1 / np.sqrt(bars), n)) * np.sqrt(252) for _ in range(300)]
    assert gp_dev.expected_max_sharpe(n, bars, 252) == pytest.approx(np.mean(maxima), rel=0.08)
    assert gp_dev.expected_max_sharpe(1, bars, 252) == 0.0
    assert gp_dev.expected_max_sharpe(5000, bars, 252) > gp_dev.expected_max_sharpe(50, bars, 252)


def test_e4_decision_needs_a_positive_median_and_a_holm_adjusted_p():
    cells = {str(k): {"trend": 0.5, "free": 0.5 + 0.1 * (k + 1), "gated": 0.5,
                      "ensemble": 0.5 - 0.05, "gated_ensemble": 0.5 + 0.01 * (-1) ** k}
             for k in range(14)}  # fmt: skip
    d = gp_dev.e4_decision(cells)
    assert d["free"]["beats_trend"]
    assert d["free"]["p_holm"] >= d["free"]["p"]
    assert not d["gated"]["beats_trend"]
    assert d["gated"]["non_inferior"]
    assert not d["ensemble"]["beats_trend"]
    assert d["ensemble"]["non_inferior"]
    assert not d["gated_ensemble"]["beats_trend"]


# --- E5: planted-signal recovery (D-101) -------------------------------------------------------


def test_e5_worlds_cover_every_condition_with_distinct_names():
    worlds = gp_dev.e5_worlds()
    assert len(worlds) == (1 + 3 * 4) * 8 == 104
    names = [n for w in worlds for n in w["names"]]
    assert len(set(names)) == len(names) == 624
    assert {(w["rule"], w["sharpe"]) for w in worlds} == {("null", 0.0)} | {
        (r, lv) for r in ("trend", "revert", "combo") for lv in (0.25, 0.5, 1.0, 2.0)
    }
    assert worlds[0]["names"][0] == "null000w1a"
    assert worlds[-1]["names"][-1] == "combo200w8f"
    dates = gp_dev.e5_dates(load_settings())
    assert str(dates[0]) == "1994-01-03"
    assert str(dates[-1]) == "2006-06-30"


def test_e5_planted_rules_are_rules_of_the_ta_grammar_and_window_evaluation_is_exact():
    """The generator decides each bar on a window; the full-array value must be the same."""
    from lpstgp.gp.evaluate import TreeEvaluator
    from lpstgp.gp.pset import build
    from lpstgp.libraries import resolve
    from lpstgp.runner import parse_tree

    lib = build(resolve("technical"))
    rng = np.random.default_rng(2)
    log_return = rng.normal(0, 0.01, 700)
    log_price = np.cumsum(log_return)
    for rule in gp_dev.E5_RULES:
        entry, exit_ = (parse_tree(t, lib) for t in gp_dev.e5_oracle(rule))
        assert lib.lookback(exit_) <= 504
        signal, lookback = gp_dev.e5_signal(rule)
        full = TreeEvaluator(lib, log_price, log_return)(entry)
        for t in (lookback - 1, 400, 699):
            window = slice(t + 1 - lookback, t + 1)
            assert signal(log_price[window], log_return[window]) == full[t]
        both = full[lookback:] + TreeEvaluator(lib, log_price, log_return)(exit_)[lookback:]
        np.testing.assert_array_equal(both, 1.0)  # exit is the complement: always long or short


def test_e5_the_engine_holds_exactly_the_planted_positions():
    from lpstgp.backtest import engine
    from lpstgp.backtest.costs import CostModel
    from lpstgp.data import synthetic
    from lpstgp.gp.evaluate import TreeEvaluator
    from lpstgp.gp.pset import build
    from lpstgp.libraries import resolve
    from lpstgp.runner import parse_tree

    lib = build(resolve("technical"))
    signal, lookback = gp_dev.e5_signal("trend")
    close, planted = synthetic.simulate(520, 1, 6, 2.0, signal, lookback)
    log_price = np.log(close[:, 0])
    log_return = np.diff(log_price, prepend=np.nan)
    ev = TreeEvaluator(lib, log_price, log_return)
    entry, exit_ = (ev(parse_tree(t, lib)) for t in gp_dev.e5_oracle("trend"))
    res = engine.run(entry, exit_, log_return, CostModel(2.0, 2.0), lag=2, mode="reverse")
    known = ~np.isnan(planted[:-2, 0])
    assert known.sum() > 250
    np.testing.assert_array_equal(res.held[2:][known], planted[:-2, 0][known])


def test_e5_match_is_agreement_beyond_chance():
    rng = np.random.default_rng(0)
    planted = np.where(rng.random(2000) < 0.2, 1.0, -1.0)  # lopsided, like the combined rule
    assert gp_dev.match(planted, planted) == pytest.approx(1.0)
    assert gp_dev.match(-planted, planted) == pytest.approx(-1.0)
    assert gp_dev.match(-np.ones(2000), planted) == 0.0  # the better constant earns no credit
    assert gp_dev.match(0.3 * planted, planted) == pytest.approx(1.0)  # sizes do not matter
    half = np.where(rng.random(2000) < 0.5, planted, rng.choice([-1.0, 1.0], 2000))
    assert 0.3 < gp_dev.match(half, planted) < 0.7
    unknown = planted.copy()
    unknown[:500] = 0.0  # bars before the planted rule is in the market do not count
    assert gp_dev.match(np.r_[-planted[:500], planted[500:]], unknown) == pytest.approx(1.0)


def _e5_rows(matches, gated_null=0):
    rows = []
    for w in range(8):
        for run in range(10):
            rows.append({"rule": "null", "sharpe": 0.0, "world": f"n{w}", "run": run,
                         "fit_sharpe": 0.6, "val_sharpe": 0.0, "val_gen0": 0.0, "val_last": 0.0,
                         "gated": w * 10 + run < gated_null})  # fmt: skip
            for (rule, level), m in matches.items():
                rows.append({"rule": rule, "sharpe": level, "world": f"{rule}{level}w{w}",
                             "run": run, "fit_sharpe": level, "val_sharpe": m * level,
                             "val_gen0": 0.0, "val_last": 0.3 + 0.01 * w, "gated": m > 0.5,
                             "match": m + 0.001 * run, "fresh_sharpe": m * level,
                             "oracle_fresh": level, "oracle_fit": level, "oracle_val": level})  # fmt: skip
    return rows


def test_e5_decision_needs_the_null_control_and_both_simple_rules_at_sharpe_two():
    levels = (0.25, 0.5, 1.0, 2.0)
    good = {(r, lv): 0.95 for r in ("trend", "revert", "combo") for lv in levels}
    good |= {("trend", 0.25): 0.2, ("revert", 0.25): 0.6, ("revert", 0.5): 0.1,
             ("combo", 2.0): 0.4}  # fmt: skip
    summary = gp_dev.e5_summary(_e5_rows(good, gated_null=4))
    assert list(summary)[:2] == ["null/0", "trend/0.25"]
    assert len(summary) == 13
    assert summary["null/0"]["gated"] == 0.05
    assert summary["null/0"]["pass_null"]
    assert summary["trend/1"]["pass_recovery"]
    assert not summary["trend/0.25"]["pass_recovery"]
    assert summary["trend/1"]["full"] == 1.0
    assert summary["trend/1"]["pass_gain"]
    decision = gp_dev.e5_decision(summary)
    # a pass below a failed level does not count: revert passes at 0.25 but fails at 0.5
    assert decision["thresholds"] == {"trend": 0.5, "revert": 1.0, "combo": None}
    assert decision["sound"]  # the combined rule is reported, but does not decide
    report = gp_dev.e5_report(summary, decision)
    assert "the machinery is sound" in report
    assert "**combo**" in report
    assert "recovered from planted Sharpe 0.5" in report
    assert "not recovered" in report
    leaky = gp_dev.e5_decision(gp_dev.e5_summary(_e5_rows(good, gated_null=5)))
    assert not leaky["null_control"]
    assert not leaky["sound"]
    missed = gp_dev.e5_decision(gp_dev.e5_summary(_e5_rows(good | {("revert", 2.0): 0.3})))
    assert missed["thresholds"]["revert"] is None
    assert not missed["sound"]
    assert "not sound" in gp_dev.e5_report(gp_dev.e5_summary(_e5_rows(good, 5)), leaky)


@pytest.mark.slow
def test_e5_rehearsal_from_data_to_report(tmp_path, monkeypatch):
    """A tiny E5 end to end on temporary paths: tier S data, the plan, cluster slices, the
    evaluation on the fit, validation and fresh samples, and the report."""
    from lpstgp.campaign.execute import execute_slice, load_plan
    from lpstgp.campaign.plan import Config
    from lpstgp.config import load_paths

    paths_file = tmp_path / "paths.toml"
    paths_file.write_text(
        f'data_dir = "{tmp_path / "data"}"\nresults_dir = "{tmp_path / "results"}"\n'
        f'reports_dir = "{tmp_path / "reports"}"\ncache_dir = "{tmp_path / "cache"}"\n'
    )
    monkeypatch.setenv("LPSTGP_PATHS", str(paths_file))
    paths, settings = load_paths(), load_settings()
    tiny = {"population": 8, "generations": 1, "elitism": 1, "hof_size": 2,
            "cache_bytes": 32 * 2**20}  # fmt: skip
    monkeypatch.setattr(gp_dev.wp4, "gp_arm", lambda name, lib, _s: Config(name, lib, gp=tiny))
    monkeypatch.setattr(gp_dev, "E5_RULES", {"trend": gp_dev.E5_RULES["trend"]})
    monkeypatch.setattr(gp_dev, "E5_SIMPLE", ("trend",))
    monkeypatch.setattr(gp_dev, "E5_LEVELS", (2.0,))
    monkeypatch.setattr(gp_dev, "E5_WORLDS", 1)
    monkeypatch.setattr(gp_dev, "E5_POOL", 2)
    monkeypatch.setattr(gp_dev, "E1_RUNS", 2)
    monkeypatch.setattr(gp_dev, "E5_FRESH_BARS", 300)

    assert gp_dev.e5_data(paths, settings, workers=1)["written"] == 2
    assert gp_dev.e5_data(paths, settings, workers=1)["written"] == 0  # complete worlds are kept
    files = sorted(p.name for p in (paths.tier_dir("S") / "processed").glob("*.parquet"))
    assert files == ["null000w1a.parquet", "null000w1b.parquet", "trend200w1a.parquet",
                     "trend200w1b.parquet"]  # fmt: skip
    plan_path = gp_dev.e5_plan(paths, settings)
    register = tmp_path / "register.csv"
    digest = gp_dev.e5_register(settings, register)
    assert gp_dev.e5_register(settings, register) == digest  # entered once
    assert register.read_text().count("gpdev-e5,e5-TA,technical,gp," + digest) == 1
    assert len(register.read_text().splitlines()) == 2
    plan = load_plan(plan_path)
    assert plan["tier"] == "S"
    assert len(plan["tasks"]) == 4
    assert {t["period"] for t in plan["tasks"]} == {"G1"}
    assert execute_slice(plan_path, paths, settings, 0, 4)["evolved"] == 4
    records = sorted((plan_path.parent / "tierS" / "records").glob("*.json.gz"))
    assert len(records) == 4

    rows = gp_dev.e5_evaluate(plan_path, paths, settings)
    assert len(rows) == 4
    null = [r for r in rows if r["rule"] == "null"]
    planted = [r for r in rows if r["rule"] == "trend"]
    assert len(null) == len(planted) == 2
    assert all("match" not in r for r in null)
    assert all(-1.0 <= r["match"] <= 1.0 for r in planted)
    assert planted[0]["oracle_fit"] == planted[1]["oracle_fit"] > 0.8  # the planted rule earns
    assert planted[0]["oracle_fresh"] > 0.8
    assert all(np.isfinite(r["fit_sharpe"]) and np.isfinite(r["val_sharpe"]) for r in rows)
    summary = gp_dev.e5_summary(rows)
    assert list(summary) == ["null/0", "trend/2"]
    decision = gp_dev.e5_decision(summary)
    assert set(decision["thresholds"]) == {"trend"}
    assert "| trend | 2 |" in gp_dev.e5_report(summary, decision)
