from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mining_sprint.raw_manifest import RawManifestError, generate_manifest, inventory_raw_files

CAPTURED_AT = datetime(2026, 8, 14, 12, 30, tzinfo=UTC)


def inventory(raw_dir: Path):
    return inventory_raw_files(raw_dir, captured_at=CAPTURED_AT)


def test_empty_raw_directory(tmp_path):
    assert inventory(tmp_path) == []


def test_one_file_has_correct_metadata_and_sha256(tmp_path):
    source = tmp_path / "rainfall.csv"
    content = b"timestamp,rainfall\n2020-10-05,12.5\n"
    source.write_bytes(content)
    record = inventory(tmp_path)[0]
    assert record["relative_path"] == record["filename"] == "rainfall.csv"
    assert record["size_bytes"] == len(content)
    assert record["sha256"] == hashlib.sha256(content).hexdigest()
    assert record["captured_at_utc"] == "2026-08-14T12:30:00Z"
    assert record["provider"] == ""


def test_nested_files_are_sorted_deterministically(tmp_path):
    paths = ["z-last.txt", "nested/b file.csv", "a-first.txt", "nested/a-file.csv"]
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    first = inventory(tmp_path)
    assert [record["relative_path"] for record in first] == ["a-first.txt", "nested/a-file.csv", "nested/b file.csv", "z-last.txt"]
    assert first == inventory(tmp_path)


def test_filename_with_spaces_and_normal_punctuation(tmp_path):
    source = tmp_path / "GPM rainfall (final), v1.0.csv"
    source.write_text("data")
    record = inventory(tmp_path)[0]
    assert record["relative_path"] == record["filename"] == source.name


def test_inventory_does_not_modify_source_files(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"immutable")
    before = source.stat()
    inventory(tmp_path)
    after = source.stat()
    assert source.read_bytes() == b"immutable"
    assert after.st_mtime_ns == before.st_mtime_ns
    assert after.st_size == before.st_size


def test_unreadable_file_has_clear_error(tmp_path, monkeypatch):
    source = tmp_path / "unreadable.bin"
    source.write_bytes(b"data")
    original_open = Path.open

    def fail_for_source(path, *args, **kwargs):
        if path == source:
            raise PermissionError("permission denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_for_source)
    with pytest.raises(RawManifestError, match="unreadable.bin.*permission denied"):
        inventory(tmp_path)


def test_generate_manifest_writes_header_for_empty_directory(tmp_path):
    raw = tmp_path / "Raw"
    raw.mkdir()
    output = tmp_path / "metadata" / "manifest.csv"
    generate_manifest(raw, output, captured_at=CAPTURED_AT)
    with output.open(newline="", encoding="utf-8") as manifest_file:
        assert list(csv.DictReader(manifest_file)) == []


def test_generate_manifest_rejects_output_inside_raw(tmp_path):
    raw = tmp_path / "Raw"
    raw.mkdir()
    with pytest.raises(RawManifestError, match="outside the Raw directory"):
        generate_manifest(raw, raw / "manifest.csv", captured_at=CAPTURED_AT)
