import pandas as pd
import pytest

from lpstgp.data import tier_c

MANIFEST = """
[[dataset]]
id = "dcgp_test"
paper = "Unit test"
files = ["dcgp/EURUSD.csv"]
date_column = "Date"
columns = { close = "Close", open = "Open" }
extra_columns = ["sentiment"]
splits = [{ train = ["2010-01-01", "2014-12-31"], test = ["2015-01-01", "2015-12-31"] }]
"""


def test_empty_tier_c(tmp_path):
    assert tier_c.load_manifest(tmp_path) == []
    assert tier_c.inventory(tmp_path) == {"files": [], "datasets": []}


def test_manifest_driven_load(tmp_path):
    (tmp_path / "manifest.toml").write_text(MANIFEST)
    (tmp_path / "dcgp").mkdir()
    pd.DataFrame(
        {"Date": ["2010-01-04", "2010-01-05"], "Open": [1.4, 1.43], "Close": [1.44, 1.436], "sentiment": [0.1, -0.2]}
    ).to_csv(tmp_path / "dcgp" / "EURUSD.csv", index=False)
    (dataset,) = tier_c.load_manifest(tmp_path)
    assert dataset.splits[0]["test"] == ["2015-01-01", "2015-12-31"]
    bars, flags, checksum = tier_c.load_file(tmp_path, dataset, dataset.files[0])
    assert bars["close"].tolist() == [1.44, 1.436] and bars["sentiment"].tolist() == [0.1, -0.2]
    assert flags.empty and len(checksum) == 64


def test_manifest_requires_close_mapping(tmp_path):
    (tmp_path / "manifest.toml").write_text(MANIFEST.replace('close = "Close", ', ""))
    with pytest.raises(ValueError, match="close"):
        tier_c.load_manifest(tmp_path)
