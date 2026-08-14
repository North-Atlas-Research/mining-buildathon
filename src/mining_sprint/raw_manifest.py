"""Inventory immutable raw data files without modifying them."""
from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

MANIFEST_COLUMNS = ("dataset_id", "relative_path", "filename", "source_url", "provider", "source_version", "source_year", "downloaded_at_utc", "captured_at_utc", "size_bytes", "sha256", "license", "event_role", "notes")
CHUNK_SIZE = 1024 * 1024


class RawManifestError(RuntimeError):
    """Raised when Raw cannot be inventoried safely."""


def inventory_raw_files(raw_directory: Path | str, *, captured_at: datetime | None = None) -> list[dict[str, str | int]]:
    """Return path-sorted manifest records, reading source files only."""
    root = Path(raw_directory)
    if not root.exists():
        raise RawManifestError(f"Raw directory does not exist: {root}")
    if not root.is_dir():
        raise RawManifestError(f"Raw path is not a directory: {root}")
    capture_time = captured_at or datetime.now(UTC)
    if capture_time.tzinfo is None or capture_time.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    timestamp = capture_time.astimezone(UTC).isoformat().replace("+00:00", "Z")
    records = []
    for path in _regular_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
            digest = _sha256(path)
        except OSError as error:
            raise RawManifestError(f"Unable to read raw file {relative!r}: {error}") from error
        records.append({"dataset_id": "", "relative_path": relative, "filename": path.name, "source_url": "", "provider": "", "source_version": "", "source_year": "", "downloaded_at_utc": "", "captured_at_utc": timestamp, "size_bytes": size, "sha256": digest, "license": "", "event_role": "", "notes": ""})
    return records


def write_manifest(records: Sequence[dict[str, str | int]], output_path: Path | str) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            writer.writerows(records)
    except OSError as error:
        raise RawManifestError(f"Unable to write manifest {destination}: {error}") from error
    return destination


def generate_manifest(raw_directory: Path | str, output_path: Path | str, *, captured_at: datetime | None = None) -> Path:
    raw_root = Path(raw_directory).resolve()
    destination = Path(output_path).resolve()
    if destination == raw_root or raw_root in destination.parents:
        raise RawManifestError("Manifest output must be outside the Raw directory")
    return write_manifest(inventory_raw_files(raw_root, captured_at=captured_at), destination)


def _regular_files(root: Path) -> Iterator[Path]:
    try:
        entries = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
    except OSError as error:
        raise RawManifestError(f"Unable to traverse raw directory {root}: {error}") from error
    for path in entries:
        if path.is_symlink():
            relative = path.relative_to(root).as_posix()
            raise RawManifestError(f"Symbolic links are not supported in Raw: {relative!r}")
        try:
            if path.is_file():
                yield path
        except OSError as error:
            relative = path.relative_to(root).as_posix()
            raise RawManifestError(f"Unable to inspect raw path {relative!r}: {error}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
