import hashlib
from pathlib import Path

from mining_sprint.external_sources import (
    EXTERNAL_SOURCE_COLUMNS,
    SOURCE_RECORD_COLUMNS,
    read_csv_records,
    validate_external_source,
    validate_source_records,
    verify_temporary_source,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "metadata" / "external_source_manifest.csv"
RECORDS_PATH = ROOT / "metadata" / "external_sources" / "odpem_portmore_shelters_2019.csv"
SOURCE_ID = "odpem_portmore_shelters_2019"
PINNED_SHA256 = "b5cad6aefeeb89fa528abc2a95bc1c564e5c731a00b2d7a11577fd444272b720"


def provenance():
    records = read_csv_records(MANIFEST_PATH, EXTERNAL_SOURCE_COLUMNS)
    assert len(records) == 1
    return records[0]


def source_records():
    return read_csv_records(RECORDS_PATH, SOURCE_RECORD_COLUMNS)


def test_external_source_provenance_is_complete_and_restricted():
    record = provenance()
    validate_external_source(record)
    assert record["source_id"] == SOURCE_ID
    assert record["redistribution_status"] == "unclear_no_redistribution"
    assert record["sha256"] == PINNED_SHA256
    assert "not be retained" in record["raw_retention_reason"]


def test_source_records_are_unique_ordered_and_have_expected_section_counts():
    counts = validate_source_records(source_records(), source_id=SOURCE_ID)
    assert counts == {
        "PORTMORE CITY MUNICIPALITY": 18,
        "Emergency Shelter outside Portmore": 2,
    }


def test_visually_verified_raw_values_are_preserved_as_text():
    records = source_records()
    by_name = {record["shelter_name_raw"]: record for record in records}
    assert by_name["Assembly of Rightousness (Priority)"]["shelter_address_raw"] == (
        "Quary Hill, St. Catherine"
    )
    assert by_name["Breaton Primary"]["capacity_raw"] == "100"
    assert by_name["Clifton Basic School (Priority)"]["capacity_raw"] == "N/A"
    assert by_name["Portsmouth Primary School(Priority)"]["areas_served_raw"] == (
        "Portsmouth, Waterford, Passagefort"
    )
    assert by_name["Kensington (Priority)"]["priority_shelter_raw"] == ""
    assert by_name["Independence City Primary"]["priority_shelter_raw"] == "Kensington"


def test_priority_markers_and_printed_priority_cells_are_both_nine():
    portmore = [
        record for record in source_records() if record["section"] == "PORTMORE CITY MUNICIPALITY"
    ]
    assert sum("(Priority)" in record["shelter_name_raw"] for record in portmore) == 9
    assert sum(bool(record["priority_shelter_raw"]) for record in portmore) == 9


def test_temporary_source_verification_uses_pinned_size_and_checksum(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"external source bytes")
    record = provenance()
    record["byte_size"] = str(source.stat().st_size)
    record["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    verify_temporary_source(source, record)
