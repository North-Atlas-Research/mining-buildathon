"""Validation helpers for externally referenced, non-retained source records."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

EXTERNAL_SOURCE_COLUMNS = (
    "source_id",
    "publisher",
    "title",
    "official_url",
    "index_url",
    "source_version",
    "server_last_modified",
    "access_date",
    "byte_size",
    "sha256",
    "redistribution_status",
    "raw_retention_reason",
)
SOURCE_RECORD_COLUMNS = (
    "source_id",
    "section",
    "source_page",
    "section_row_ordinal",
    "document_row_ordinal",
    "parish_raw",
    "local_authority_raw",
    "shelter_name_raw",
    "shelter_address_raw",
    "community_raw",
    "priority_shelter_raw",
    "capacity_raw",
    "zone_raw",
    "areas_served_raw",
)
ALLOWED_REDISTRIBUTION_STATUSES = {"not_authorized", "unclear_no_redistribution"}


class ExternalSourceError(ValueError):
    """Raised when external-source provenance or extracted records are invalid."""


def read_csv_records(path: Path, expected_columns: tuple[str, ...]) -> list[dict[str, str]]:
    """Read a UTF-8 CSV and require its exact ordered schema."""
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise ExternalSourceError(f"Unexpected columns in {path}: {reader.fieldnames}")
        return list(reader)


def validate_external_source(record: dict[str, str]) -> None:
    """Validate complete provenance for a source intentionally not retained in Raw."""
    missing = [column for column in EXTERNAL_SOURCE_COLUMNS if not record.get(column)]
    if missing:
        raise ExternalSourceError(f"External-source provenance is incomplete: {missing}")
    if record["redistribution_status"] not in ALLOWED_REDISTRIBUTION_STATUSES:
        raise ExternalSourceError("External source must carry a no-redistribution status")
    if len(record["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in record["sha256"]):
        raise ExternalSourceError("External-source SHA-256 is malformed")
    if int(record["byte_size"]) <= 0:
        raise ExternalSourceError("External-source byte size must be positive")


def validate_source_records(records: list[dict[str, str]], *, source_id: str) -> Counter[str]:
    """Validate field-preserving rows without interpreting capacity or other raw values."""
    if not records:
        raise ExternalSourceError("Source-record extraction is empty")
    identities: set[tuple[str, str]] = set()
    document_ordinals: list[int] = []
    section_ordinals: dict[str, list[int]] = {}
    for record in records:
        if record["source_id"] != source_id:
            raise ExternalSourceError(f"Unexpected source_id: {record['source_id']}")
        required_raw = [
            "parish_raw",
            "local_authority_raw",
            "shelter_name_raw",
            "shelter_address_raw",
            "community_raw",
            "capacity_raw",
            "zone_raw",
            "areas_served_raw",
        ]
        missing = [column for column in required_raw if record[column] == ""]
        if missing:
            raise ExternalSourceError(f"Required printed values are blank: {missing}")
        identity = (record["section"], record["section_row_ordinal"])
        if identity in identities:
            raise ExternalSourceError(f"Duplicate source-record identity: {identity}")
        identities.add(identity)
        document_ordinals.append(int(record["document_row_ordinal"]))
        section_ordinals.setdefault(record["section"], []).append(
            int(record["section_row_ordinal"])
        )
    if document_ordinals != list(range(1, len(records) + 1)):
        raise ExternalSourceError("Document row ordinals are not contiguous and ordered")
    for section, ordinals in section_ordinals.items():
        if ordinals != list(range(1, len(ordinals) + 1)):
            raise ExternalSourceError(f"Section row ordinals are invalid for {section}")
    return Counter(record["section"] for record in records)


def verify_temporary_source(path: Path, provenance: dict[str, str]) -> None:
    """Verify a temporary download against pinned external-source bytes and checksum."""
    size = path.stat().st_size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if size != int(provenance["byte_size"]):
        raise ExternalSourceError(f"Source byte-size mismatch: {size}")
    if digest != provenance["sha256"]:
        raise ExternalSourceError(f"Source checksum mismatch: {digest}")
