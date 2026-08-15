"""Validation for WS25-004 shelter identity and geolocation review artifacts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from mining_sprint.external_sources import (
    SOURCE_RECORD_COLUMNS,
    ExternalSourceError,
    read_csv_records,
)

IDENTITY_COLUMNS = (
    "source_record_id",
    "canonical_candidate_id",
    "source_name",
    "normalized_display_name_candidate",
    "identity_evidence",
    "possible_duplicate_group",
    "identity_confidence",
    "manual_review_status",
    "decision_note",
)
LOCATION_COLUMNS = (
    "location_candidate_id",
    "source_record_id",
    "canonical_candidate_id",
    "candidate_status",
    "source_url",
    "publisher",
    "access_date",
    "source_latitude",
    "source_longitude",
    "source_crs",
    "derivation_method",
    "evidence_description",
    "precision_class",
    "confidence",
    "manual_review_requirement",
    "source_conflicts",
    "nominatim_exact_query",
    "nominatim_retrieval_timestamp_utc",
    "osm_type",
    "osm_id",
    "osm_element_url",
    "returned_display_name",
    "returned_class",
    "returned_type",
    "coordinate_representation",
    "licence_identifier",
    "evidence_observation_date",
)
REJECTED_LOCATION_COLUMNS = (
    "rejected_candidate_id",
    "source_record_id",
    "canonical_candidate_id",
    "discovery_source_url",
    "discovery_publisher",
    "exact_query_or_input",
    "retrieval_timestamp_utc",
    "osm_type",
    "osm_id",
    "osm_element_url",
    "returned_display_name",
    "returned_class",
    "returned_type",
    "source_latitude",
    "source_longitude",
    "source_crs",
    "licence_identifier",
    "evidence_observation_date",
    "rejection_reason",
)
PRIORITY_COLUMNS = (
    "source_record_id",
    "canonical_candidate_id",
    "source_name",
    "source_name_priority_marker",
    "priority_shelter_raw",
    "normalized_priority_interpretation",
    "interpretation_evidence",
    "manual_review_status",
    "decision_note",
)
TRANSCRIPTION_SHA256 = "5a35d4e2f9672d9b15e51341c374a0cc5d1bd0dafd5d39d2d40c915347cb4143"


def expected_source_record_id(record: dict[str, str]) -> str:
    """Return the stable identifier derived only from source section and row order."""
    prefix = "pm" if record["section"] == "PORTMORE CITY MUNICIPALITY" else "out"
    return f"odpem2019-{prefix}-{int(record['section_row_ordinal']):03d}"


def validate_identity_crosswalk(
    source_records: list[dict[str, str]], identities: list[dict[str, str]]
) -> None:
    """Require a one-to-one, order-stable identity candidate for every source row."""
    if len(source_records) != 20 or len(identities) != len(source_records):
        raise ExternalSourceError("Identity crosswalk must preserve all 20 source records")
    source_ids = [expected_source_record_id(record) for record in source_records]
    identity_ids = [record["source_record_id"] for record in identities]
    if identity_ids != source_ids or len(set(identity_ids)) != len(identity_ids):
        raise ExternalSourceError("Source-record identifiers are not unique and source-ordered")
    candidate_ids = [record["canonical_candidate_id"] for record in identities]
    expected_candidates = [f"shelter_candidate_{index:04d}" for index in range(1, 21)]
    if candidate_ids != expected_candidates or len(set(candidate_ids)) != 20:
        raise ExternalSourceError("Canonical candidate identifiers are not stable and unique")
    for source, identity in zip(source_records, identities, strict=True):
        if identity["source_name"] != source["shelter_name_raw"]:
            raise ExternalSourceError("Identity crosswalk changed a source shelter name")
        if not identity["identity_evidence"] or not identity["decision_note"]:
            raise ExternalSourceError("Identity evidence and decision note are required")


def validate_location_candidates(
    identities: list[dict[str, str]], locations: list[dict[str, str]]
) -> Counter[str]:
    """Validate candidate coordinates without selecting or inventing geometry."""
    candidate_ids = {record["canonical_candidate_id"] for record in identities}
    represented = {record["canonical_candidate_id"] for record in locations}
    if represented != candidate_ids:
        raise ExternalSourceError("Every shelter candidate must have a location review record")
    location_ids = [record["location_candidate_id"] for record in locations]
    if len(location_ids) != len(set(location_ids)):
        raise ExternalSourceError("Location candidate identifiers must be unique")
    for record in locations:
        if record["manual_review_requirement"] != "required":
            raise ExternalSourceError("All preliminary locations require manual review")
        if not all(
            record[field]
            for field in (
                "source_url",
                "publisher",
                "access_date",
                "derivation_method",
                "evidence_description",
                "precision_class",
                "confidence",
                "source_conflicts",
            )
        ):
            raise ExternalSourceError("Location evidence is incomplete")
        coordinates = (record["source_latitude"], record["source_longitude"])
        audit_fields = (
            "nominatim_exact_query",
            "nominatim_retrieval_timestamp_utc",
            "coordinate_representation",
            "licence_identifier",
            "evidence_observation_date",
        )
        if not all(record[field] for field in audit_fields):
            raise ExternalSourceError("Nominatim audit metadata is incomplete")
        if record["licence_identifier"] != "ODbL-1.0":
            raise ExternalSourceError("OSM evidence must identify the ODbL licence")
        if record["candidate_status"] == "candidate":
            if not all(coordinates) or record["source_crs"] != "EPSG:4326":
                raise ExternalSourceError("Coordinate candidates require EPSG:4326 coordinates")
            latitude, longitude = map(float, coordinates)
            if not (17.0 <= latitude <= 19.0 and -79.0 <= longitude <= -76.0):
                raise ExternalSourceError("Coordinate candidate falls outside Jamaica")
            osm_fields = (
                "osm_type",
                "osm_id",
                "osm_element_url",
                "returned_display_name",
                "returned_class",
                "returned_type",
            )
            if not all(record[field] for field in osm_fields):
                raise ExternalSourceError("OSM coordinate response metadata is incomplete")
            expected_url = f"https://www.openstreetmap.org/{record['osm_type']}/{record['osm_id']}"
            if record["source_url"] != expected_url or record["osm_element_url"] != expected_url:
                raise ExternalSourceError("OSM element URL does not match its type and identifier")
            expected_representation = {
                "node": "osm_node",
                "way": "computed_way_centroid",
            }.get(record["osm_type"])
            if record["coordinate_representation"] != expected_representation:
                raise ExternalSourceError("OSM coordinate representation is inconsistent")
        elif record["candidate_status"] == "unresolved":
            if any(coordinates) or record["source_crs"]:
                raise ExternalSourceError("Unresolved locations must remain geometry-null")
            if record["coordinate_representation"] != "no_result":
                raise ExternalSourceError("Unresolved Nominatim searches must record no_result")
        else:
            raise ExternalSourceError(f"Unexpected location status: {record['candidate_status']}")
    return Counter(record["candidate_status"] for record in locations)


def validate_priority_review(
    source_records: list[dict[str, str]], priorities: list[dict[str, str]]
) -> Counter[str]:
    """Ensure priority interpretation never comes from the populated column alone."""
    if len(priorities) != len(source_records):
        raise ExternalSourceError("Priority review must preserve every source record")
    for source, priority in zip(source_records, priorities, strict=True):
        if priority["source_record_id"] != expected_source_record_id(source):
            raise ExternalSourceError("Priority review is not source-ordered")
        if priority["source_name"] != source["shelter_name_raw"]:
            raise ExternalSourceError("Priority review changed a source shelter name")
        if priority["priority_shelter_raw"] != source["priority_shelter_raw"]:
            raise ExternalSourceError("Priority review changed a printed Priority Shelter cell")
        has_marker = "(Priority)" in source["shelter_name_raw"]
        if priority["source_name_priority_marker"] != str(has_marker).lower():
            raise ExternalSourceError("Priority marker transcription is inconsistent")
        if (
            priority["normalized_priority_interpretation"] == "priority_supported"
            and not has_marker
        ):
            raise ExternalSourceError("Priority cannot be inferred from the populated column alone")
        if priority["normalized_priority_interpretation"] == "confirmed_non_priority":
            raise ExternalSourceError("Source silence cannot establish confirmed non-priority")
    return Counter(record["normalized_priority_interpretation"] for record in priorities)


def load_resolution_inputs(root: Path) -> dict[str, list[dict[str, str]]]:
    """Load the tracked WS25-004 transcription and review tables."""
    source_root = root / "metadata" / "external_sources"
    return {
        "source": read_csv_records(
            source_root / "odpem_portmore_shelters_2019.csv", SOURCE_RECORD_COLUMNS
        ),
        "identity": read_csv_records(
            source_root / "odpem_portmore_shelters_2019_identity_crosswalk.csv",
            IDENTITY_COLUMNS,
        ),
        "location": read_csv_records(
            source_root / "odpem_portmore_shelters_2019_location_candidates.csv",
            LOCATION_COLUMNS,
        ),
        "rejected_location": read_csv_records(
            source_root / "odpem_portmore_shelters_2019_location_rejected_candidates.csv",
            REJECTED_LOCATION_COLUMNS,
        ),
        "priority": read_csv_records(
            source_root / "odpem_portmore_shelters_2019_priority_review_queue.csv",
            PRIORITY_COLUMNS,
        ),
    }
