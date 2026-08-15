import hashlib
from collections import Counter
from pathlib import Path

from mining_sprint.external_sources import read_csv_records
from mining_sprint.shelter_resolution import (
    IDENTITY_COLUMNS,
    REJECTED_LOCATION_COLUMNS,
    TRANSCRIPTION_SHA256,
    load_resolution_inputs,
    validate_identity_crosswalk,
    validate_location_candidates,
    validate_priority_review,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "metadata" / "external_sources"


def test_transcription_is_byte_unchanged_from_approved_checkpoint():
    path = SOURCE_ROOT / "odpem_portmore_shelters_2019.csv"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == TRANSCRIPTION_SHA256


def test_identity_crosswalk_preserves_all_records_and_has_stable_ids():
    inputs = load_resolution_inputs(ROOT)
    validate_identity_crosswalk(inputs["source"], inputs["identity"])
    assert len(inputs["identity"]) == 20
    assert all(
        identity["canonical_candidate_id"].startswith("shelter_candidate_")
        for identity in inputs["identity"]
    )


def test_no_possible_duplicates_are_silently_merged():
    identities = read_csv_records(
        SOURCE_ROOT / "odpem_portmore_shelters_2019_identity_crosswalk.csv",
        IDENTITY_COLUMNS,
    )
    assert all(record["possible_duplicate_group"] == "" for record in identities)
    duplicate_queue = SOURCE_ROOT / "odpem_portmore_shelters_2019_duplicate_review_queue.csv"
    assert len(duplicate_queue.read_text(encoding="utf-8").splitlines()) == 1


def test_locations_include_candidates_and_geometry_null_unresolved_records():
    inputs = load_resolution_inputs(ROOT)
    counts = validate_location_candidates(inputs["identity"], inputs["location"])
    assert counts == {"candidate": 16, "unresolved": 7}
    assert len({record["canonical_candidate_id"] for record in inputs["location"]}) == 20


def test_priority_displacement_remains_unresolved_and_unrepaired():
    inputs = load_resolution_inputs(ROOT)
    counts = validate_priority_review(inputs["source"], inputs["priority"])
    assert counts == {
        "priority_supported": 9,
        "not_indicated_by_source": 8,
        "unresolved": 3,
    }
    by_id = {record["source_record_id"]: record for record in inputs["priority"]}
    independence = by_id["odpem2019-pm-013"]
    kensington = by_id["odpem2019-pm-014"]
    assert independence["priority_shelter_raw"] == "Kensington"
    assert independence["normalized_priority_interpretation"] == "unresolved"
    assert kensington["priority_shelter_raw"] == ""
    assert kensington["normalized_priority_interpretation"] == "priority_supported"


def test_identity_and_location_confidence_are_separate_and_defined():
    inputs = load_resolution_inputs(ROOT)
    assert Counter(row["identity_confidence"] for row in inputs["identity"]) == {
        "high": 16,
        "medium": 2,
        "low": 2,
    }
    accepted_entities = {
        row["canonical_candidate_id"]: row["confidence"]
        for row in inputs["location"]
        if row["candidate_status"] == "candidate"
    }
    assert Counter(accepted_entities.values()) == {"medium": 13}
    assert sum(row["candidate_status"] == "unresolved" for row in inputs["location"]) == 7


def test_osm_candidates_preserve_auditable_nominatim_metadata():
    inputs = load_resolution_inputs(ROOT)
    validate_location_candidates(inputs["identity"], inputs["location"])
    osm_rows = [row for row in inputs["location"] if row["candidate_status"] == "candidate"]
    assert len(osm_rows) == 16
    assert all(row["licence_identifier"] == "ODbL-1.0" for row in osm_rows)
    assert all(row["nominatim_exact_query"] for row in osm_rows)
    assert all(row["nominatim_retrieval_timestamp_utc"] for row in osm_rows)
    assert all(row["evidence_observation_date"] == "2026-08-15" for row in osm_rows)
    assert {(row["osm_type"], row["coordinate_representation"]) for row in osm_rows} <= {
        ("node", "osm_node"),
        ("way", "computed_way_centroid"),
    }


def test_rejected_location_evidence_is_retained_with_reasons():
    rejected = read_csv_records(
        SOURCE_ROOT / "odpem_portmore_shelters_2019_location_rejected_candidates.csv",
        REJECTED_LOCATION_COLUMNS,
    )
    assert len(rejected) == 5
    assert all(row["rejection_reason"] for row in rejected)
    osm_rows = [row for row in rejected if row["osm_id"]]
    assert len(osm_rows) == 4
    assert all(row["licence_identifier"] == "ODbL-1.0" for row in osm_rows)


def test_priority_supported_geometry_null_queue_is_explicit():
    inputs = load_resolution_inputs(ROOT)
    supported = {
        row["source_record_id"]
        for row in inputs["priority"]
        if row["normalized_priority_interpretation"] == "priority_supported"
    }
    located = {
        row["source_record_id"]
        for row in inputs["location"]
        if row["candidate_status"] == "candidate"
    }
    assert supported - located == {
        "odpem2019-pm-002",
        "odpem2019-pm-007",
        "odpem2019-pm-011",
        "odpem2019-pm-017",
    }
    assert all(
        row["normalized_priority_interpretation"] != "confirmed_non_priority"
        for row in inputs["priority"]
    )


def test_documentation_records_osm_attribution_policy_and_identifier_contract():
    text = (ROOT / "docs" / "ws25_004_shelter_identity_geolocation.md").read_text()
    assert "[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright)" in text
    assert "https://operations.osmfoundation.org/policies/nominatim/" in text
    assert "one-time controlled small-batch pass" in text
    assert "final canonical shelter ID will be assigned only" in text
    assert "does not prove 2019 or 2020 shelter operation" in text
