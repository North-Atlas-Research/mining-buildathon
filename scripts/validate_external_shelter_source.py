"""Validate WS25-004 provenance and field-preserving factual transcription."""

from __future__ import annotations

import argparse
from pathlib import Path

from mining_sprint.external_sources import (
    EXTERNAL_SOURCE_COLUMNS,
    SOURCE_RECORD_COLUMNS,
    read_csv_records,
    validate_external_source,
    validate_source_records,
    verify_temporary_source,
)
from mining_sprint.shelter_resolution import (
    load_resolution_inputs,
    validate_identity_crosswalk,
    validate_location_candidates,
    validate_priority_review,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "metadata" / "external_source_manifest.csv"
DEFAULT_RECORDS = ROOT / "metadata" / "external_sources" / "odpem_portmore_shelters_2019.csv"
SOURCE_ID = "odpem_portmore_shelters_2019"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument(
        "--temporary-source-pdf",
        type=Path,
        help="Optional temporary external PDF to verify; never copied into Raw",
    )
    args = parser.parse_args()

    provenance_records = read_csv_records(args.manifest, EXTERNAL_SOURCE_COLUMNS)
    matching = [record for record in provenance_records if record["source_id"] == SOURCE_ID]
    if len(matching) != 1:
        raise SystemExit(f"Expected one {SOURCE_ID} provenance record; found {len(matching)}")
    provenance = matching[0]
    validate_external_source(provenance)

    source_records = read_csv_records(args.records, SOURCE_RECORD_COLUMNS)
    counts = validate_source_records(source_records, source_id=SOURCE_ID)
    if args.temporary_source_pdf:
        verify_temporary_source(args.temporary_source_pdf, provenance)

    print(f"Validated external source: {SOURCE_ID}")
    print(f"Pinned SHA-256: {provenance['sha256']}")
    for section, count in counts.items():
        print(f"{section}: {count} records")

    resolution = load_resolution_inputs(ROOT)
    validate_identity_crosswalk(resolution["source"], resolution["identity"])
    location_counts = validate_location_candidates(resolution["identity"], resolution["location"])
    priority_counts = validate_priority_review(resolution["source"], resolution["priority"])
    print(f"Identity candidates: {len(resolution['identity'])}")
    print(f"Location review: {dict(location_counts)}")
    print(f"Priority review: {dict(priority_counts)}")


if __name__ == "__main__":
    main()
