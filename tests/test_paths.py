from pathlib import Path

from mining_sprint import paths


def test_data_root_can_be_overridden(monkeypatch):
    monkeypatch.setenv("PROJECT_DATA_ROOT", "/tmp/example-data")
    assert paths.data_root() == Path("/tmp/example-data")
    assert paths.raw_dir() == Path("/tmp/example-data/Raw")
    assert paths.processed_dir() == Path("/tmp/example-data/Processed")
