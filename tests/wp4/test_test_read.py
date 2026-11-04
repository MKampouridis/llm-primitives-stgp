"""WP4's test read (protocol_wp4 §6-7): the frozen-test sandbox, the one-sided tests, the
primary family, and the per-run series storage."""

from datetime import date

import numpy as np
import pytest
from tests.leakage.test_sandbox import LMAX, _frame, _store
from tests.leakage.test_wp2_horizon import _committed_manifest

from lpstgp import wp4_test
from lpstgp.analysis import wp4 as analysis
from lpstgp.analysis.inference import one_sided_bootstrap
from lpstgp.config import load_settings
from lpstgp.freeze import FreezeManifest, write_manifest
from lpstgp.sandbox import Sandbox, SealedPeriodError
from lpstgp.splits import Stage, all_periods

SETTINGS = load_settings()
PERIODS = all_periods(SETTINGS)
P01, P02 = PERIODS["P01"], PERIODS["P02"]


def _manifest_naming(tmp_path, periods):
    import subprocess

    tmp_path.mkdir(parents=True, exist_ok=True)
    m = _committed_manifest(tmp_path)  # a committed repo with one manifest
    path = m.path
    write_manifest(path, {"x": "y"}, {"test_periods": sorted(periods)})
    git = ["git", "-C", str(path.parent)]
    subprocess.run([*git, "add", path.name], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "wp4"], check=True)
    return FreezeManifest.load_committed(path, repo=path.parent)


def _claimed(manifest):
    from lpstgp.freeze import claim_test_read

    claim_test_read(manifest.path.parent / "test_claim.json", manifest)
    return manifest


def _store_capped(tmp_path):
    store = _store(tmp_path, "s", _frame())
    store.max_horizon = SETTINGS["leakage"]["max_horizon"]
    return store


def test_frozen_test_needs_a_committed_manifest_naming_the_period(tmp_path):
    store = _store_capped(tmp_path)
    manifest = _manifest_naming(tmp_path, ["P01", "P02"])
    with pytest.raises(SealedPeriodError, match="claimed"):  # the claim comes first (D-087)
        Sandbox.open_frozen_test(
            store, P01, ["TST"], LMAX, test_periods=(P01, P02), manifest=manifest
        )
    _claimed(manifest)
    box = Sandbox.open_frozen_test(
        store, P01, ["TST"], LMAX, test_periods=(P01, P02), manifest=manifest
    )
    assert box.stage is Stage.TEST
    assert box["TST"].dates[-1] < np.datetime64(P01.test_end)
    with pytest.raises(SealedPeriodError, match="manifest"):
        Sandbox.open_frozen_test(store, P01, ["TST"], LMAX, test_periods=(P01,), manifest=None)
    with pytest.raises(SealedPeriodError, match="not a test period"):  # not named in it
        Sandbox.open_frozen_test(
            store, PERIODS["P03"], ["TST"], LMAX, test_periods=(PERIODS["P03"],),
            manifest=manifest,
        )  # fmt: skip
    with pytest.raises(SealedPeriodError, match="not a test period"):  # list differs
        Sandbox.open_frozen_test(store, P01, ["TST"], LMAX, test_periods=(P01,), manifest=manifest)


def test_pilots_and_pc_have_no_wp4_read_under_these_settings(tmp_path):
    store = _store_capped(tmp_path)
    pl = _claimed(_manifest_naming(tmp_path / "a", ["PL1"]))
    with pytest.raises(SealedPeriodError, match="no WP4 test read"):
        Sandbox.open_frozen_test(
            store, PERIODS["PL1"], ["TST"], LMAX, test_periods=(PERIODS["PL1"],), manifest=pl
        )
    pc = _claimed(_manifest_naming(tmp_path / "b", ["PC"]))
    with pytest.raises(SealedPeriodError, match="cap"):  # PC's test year is past the cap
        Sandbox.open_frozen_test(
            store, PERIODS["PC"], ["TST"], LMAX, test_periods=(PERIODS["PC"],), manifest=pc
        )


def _returns(rng, n, mean=0.0, sd=0.01):
    return rng.normal(mean, sd, n)


def test_one_sided_bootstrap_directions_and_margin():
    rng = np.random.default_rng(1)
    n = 2500
    base = _returns(rng, n)
    better = base + 0.0012 + _returns(rng, n, sd=0.002)
    assert one_sided_bootstrap(better, base, resamples=400).p_value < 0.05
    assert one_sided_bootstrap(base, better, resamples=400).p_value > 0.95
    near = base - 0.00005 + _returns(rng, n, sd=0.0005)  # a little worse
    assert one_sided_bootstrap(near, base, margin=0.0, resamples=400).p_value > 0.5
    assert one_sided_bootstrap(near, base, margin=-0.3, resamples=400).p_value < 0.05


def _series(rng, start, n, mean=0.0):
    dates = np.arange(np.datetime64(start), np.datetime64(start) + n).astype("datetime64[D]")
    return dates, _returns(rng, n, mean)


def test_primary_family_has_eight_holm_adjusted_comparisons():
    rng = np.random.default_rng(2)
    arms = {c for comp in analysis.COMPARISONS for c in (comp.a, comp.b)}
    portfolios = {a: _series(rng, "2008-07-01", 1500) for a in arms}
    out = analysis.primary(portfolios, resamples=200)
    assert len(out["comparisons"]) == 8
    p = [r["p_value"] for r in out["comparisons"]]
    holm = [r["p_holm"] for r in out["comparisons"]]
    assert all(h >= q for h, q in zip(holm, p, strict=True))
    (h2a,) = [r for r in out["comparisons"] if r["hypothesis"] == "H2a"]
    assert h2a["margin"] == -analysis.NON_INFERIORITY_MARGIN


def test_concatenation_refuses_overlapping_test_years():
    rng = np.random.default_rng(3)
    a, b = _series(rng, "2008-07-01", 10), _series(rng, "2008-07-05", 10)
    with pytest.raises(ValueError, match="overlap"):
        analysis.concatenate({"P01": a, "P02": b}, ["P01", "P02"])
    c = _series(rng, "2009-07-01", 10)
    assert len(analysis.concatenate({"P01": a, "P02": c}, ["P01", "P02"])[0]) == 20


def _evaluation(rng, n=30):
    d, _ = _series(rng, "2010-07-01", n)
    ev = wp4_test.Evaluation(lag=2, cost_multiplier=1.0)
    simple = _returns(rng, n)
    ev.market["SPX"] = {"simple": simple, "buy": np.full(n, 2e-4), "sell": np.full(n, 3e-4)}
    for key in (("arm3", "SPX", 1), ("arm3", "SPX", 2), ("BH", "SPX", 0)):
        decisions = (rng.random(n) < 0.5).astype(np.int8)
        ev.decisions[key] = decisions
        ev.series[key] = (d, wp4_test.replay(decisions, ev.market["SPX"], 2))
    return ev


def test_series_are_saved_per_run_and_reload(tmp_path):
    ev = _evaluation(np.random.default_rng(4))
    path = tmp_path / "P01.npz"
    wp4_test.save(path, ev)
    back = wp4_test.load(path)
    assert (back.lag, back.cost_multiplier) == (2, 1.0)
    assert set(back.series) == set(ev.series) == set(back.decisions)
    for k in ev.series:
        np.testing.assert_array_equal(back.series[k][0], ev.series[k][0])
        np.testing.assert_allclose(back.series[k][1], ev.series[k][1], rtol=1e-6, atol=1e-9)
        np.testing.assert_array_equal(back.decisions[k], ev.decisions[k])
    for f in ("simple", "buy", "sell"):
        np.testing.assert_array_equal(back.market["SPX"][f], ev.market["SPX"][f])
    assert set(wp4_test.portfolios(back)) == {"arm3", "BH"}


def test_replay_matches_the_backtest_engine_at_every_lag_and_cost():
    """The saved decisions and market arrays give the secondary analyses (cost sweep, lag 1)
    exactly as a fresh backtest would, so none of them needs a second read (D-087)."""
    from lpstgp.backtest import engine
    from lpstgp.backtest.costs import CostModel

    rng = np.random.default_rng(5)
    n, start = 400, 150
    entry = (rng.random(n) < 0.1).astype(float)
    exit_ = (rng.random(n) < 0.1).astype(float)
    entry[rng.random(n) < 0.05] = np.nan
    lr = rng.normal(0, 0.01, n)
    lr[rng.random(n) < 0.02] = np.nan
    decisions = engine.decide(entry, exit_, start)[start:].astype(np.int8)
    simple = np.where(np.isnan(lr), 0.0, np.expm1(np.nan_to_num(lr)))[start:]
    for lag in (1, 2):
        for mult in (0.5, 1.0, 2.0, 3.0):
            costs = CostModel(2.0, 3.0, mult)
            want = engine.run(entry, exit_, lr, costs, active_from=start, lag=lag).net[start:]
            buy, sell = CostModel(2.0, 3.0, 1.0).rates(n - start)
            market = {"simple": simple, "buy": buy, "sell": sell}
            got = wp4_test.replay(decisions, market, lag, cost_multiplier=mult)
            np.testing.assert_allclose(got, want, rtol=0, atol=1e-15)


def test_check_replay_catches_a_series_the_saved_arrays_do_not_reproduce():
    ev = _evaluation(np.random.default_rng(6))
    wp4_test.check_replay(ev)
    d, v = ev.series[("arm3", "SPX", 1)]
    ev.series[("arm3", "SPX", 1)] = (d, v + 1e-6)
    with pytest.raises(AssertionError, match="replay"):
        wp4_test.check_replay(ev)


def test_the_rehearsal_reads_only_the_validation_year(tmp_path):
    store = _store_capped(tmp_path)
    box = Sandbox.open(store, P01, Stage.VALIDATE, ["TST"], LMAX)
    rehearsal = wp4_test.as_test(box)
    assert rehearsal.period.test_start == P01.val_start
    assert box["TST"].dates[-1] < np.datetime64(P01.test_start)
    with pytest.raises(ValueError, match="VALIDATE"):
        wp4_test.as_test(Sandbox.open(store, P01, Stage.FIT, ["TST"], LMAX))
    assert date(2008, 7, 1) == P01.test_start
