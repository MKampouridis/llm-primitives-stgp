from pathlib import Path

import pytest

from lpstgp.config import REPO_ROOT, ConfigError, load_paths

LOCAL = 'data_dir = "data"\nresults_dir = "results"\nreports_dir = "reports"\ncache_dir = "cache"\n'


def test_relative_paths_resolve_against_the_repository(tmp_path: Path, monkeypatch):
    source = tmp_path / "paths.toml"
    source.write_text(LOCAL, encoding="utf-8")
    monkeypatch.chdir(tmp_path)  # the working directory must not matter
    paths = load_paths(source)
    assert paths.data_dir == REPO_ROOT / "data"
    assert paths.reports_dir == REPO_ROOT / "reports"
    assert paths.backup_dir is None


def test_backup_dir_may_be_cloud_synced_but_working_paths_may_not(tmp_path: Path):
    box = "~/Library/CloudStorage/Box-Box/project"
    source = tmp_path / "paths.toml"
    source.write_text(LOCAL + f'backup_dir = "{box}"\n', encoding="utf-8")
    assert load_paths(source).backup_dir == Path(box).expanduser().resolve()
    source.write_text(LOCAL.replace('"results"', f'"{box}/results"'), encoding="utf-8")
    with pytest.raises(ConfigError, match="results_dir"):
        load_paths(source)
