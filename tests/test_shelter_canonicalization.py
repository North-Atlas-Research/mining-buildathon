import csv
from pathlib import Path

import geopandas as gpd

from mining_sprint.paths import interim_dir, processed_dir, raw_dir
from mining_sprint.shelter_canonicalization import (
    LAYER_NAME,
    ShelterPaths,
    canonicalize_shelters,
    parse_capacity,
    stable_shelter_id,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "metadata/external_sources/odpem_portmore_shelters_2019.csv"


def _generated(tmp_path: Path):
    outputs = tmp_path / "Outputs/ws25-004"
    paths = ShelterPaths(
        repository_root=ROOT,
        raw_root=raw_dir(),
        boundary=processed_dir() / "region/portmore_boundary.gpkg",
        edge_review=interim_dir() / "region/portmore_boundary_edge_review_750m.gpkg",
        context_buffer=interim_dir() / "region/portmore_acquisition_context_buffer_2000m.gpkg",
        canonical=tmp_path / "Processed/shelters/portmore_shelters_2019.gpkg",
        preview=outputs / "portmore_shelters_2019_preview_epsg4326.geojson",
        validation=outputs / "validation.json",
        lineage=outputs / "lineage.json",
        review_queue=outputs / "consolidated_review_queue.csv",
    )
    validation = canonicalize_shelters(paths)
    return paths, validation, gpd.read_file(paths.canonical, layer=LAYER_NAME)


def test_shelter_id_is_stable_and_independent_of_mutable_attributes():
    source_id = "odpem2019-pm-001"
    assert stable_shelter_id(source_id) == stable_shelter_id(source_id)
    assert stable_shelter_id(source_id) != stable_shelter_id("odpem2019-pm-002")
    assert "ascot" not in stable_shelter_id(source_id)


def test_capacity_parser_never_converts_missing_to_zero():
    assert parse_capacity("120") == (120, "stated")
    assert parse_capacity("N/A") == (None, "missing")
    assert parse_capacity("") == (None, "missing")
    assert parse_capacity("about 20") == (None, "ambiguous")


def test_canonical_artifacts_preserve_records_nulls_and_lineage(tmp_path):
    paths, validation, frame = _generated(tmp_path)
    assert validation["status"] == "passed"
    assert len(frame) == 20
    assert frame["shelter_id"].nunique() == 20
    assert frame["source_record_id"].nunique() == 20
    assert frame.geometry.isna().sum() == 7
    assert frame.loc[frame.geometry.notna()].geometry.is_valid.all()
    nulls = frame.loc[frame.geometry.isna()]
    assert nulls["spatial_classification_status"].eq("unknown").all()
    assert nulls["inside_operational_boundary"].isna().all()
    assert nulls["in_boundary_edge_review_band"].isna().all()
    assert nulls["in_acquisition_context_buffer"].isna().all()
    assert frame["operational_usable_capacity"].isna().all()
    assert (
        frame.loc[frame["capacity_status"] == "missing", "historical_listed_capacity"].isna().all()
    )
    assert not (frame["historical_listed_capacity"] == 0).any()
    outside = frame.loc[frame["source_section_raw"] == "Emergency Shelter outside Portmore"]
    assert len(outside) == 2
    assert outside["source_defined_outside_portmore_emergency_shelter"].all()
    assert outside["in_acquisition_context_buffer"].isin([False, "False", 0]).all()
    assert paths.preview.exists() and paths.lineage.exists() and paths.review_queue.exists()


def test_all_raw_fields_round_trip_exactly(tmp_path):
    _, _, frame = _generated(tmp_path)
    with SOURCE.open(newline="", encoding="utf-8") as source_file:
        source = list(csv.DictReader(source_file))
    mappings = {
        "source_id": "source_id",
        "section": "source_section_raw",
        "parish_raw": "parish_raw",
        "local_authority_raw": "local_authority_raw",
        "shelter_name_raw": "source_name_raw",
        "shelter_address_raw": "shelter_address_raw",
        "community_raw": "community_raw",
        "priority_shelter_raw": "priority_shelter_raw",
        "capacity_raw": "capacity_raw",
        "zone_raw": "zone_raw",
        "areas_served_raw": "areas_served_raw",
    }
    for original, canonical in zip(source, frame.to_dict("records"), strict=True):
        for source_field, canonical_field in mappings.items():
            assert original[source_field] == canonical[canonical_field]
        assert int(original["source_page"]) == canonical["source_page"]
        assert int(original["section_row_ordinal"]) == canonical["source_section_row_ordinal"]
        assert int(original["document_row_ordinal"]) == canonical["source_document_row_ordinal"]
    assert (
        frame["source_checksum_sha256"]
        .eq("b5cad6aefeeb89fa528abc2a95bc1c564e5c731a00b2d7a11577fd444272b720")
        .all()
    )
    assert (
        frame["source_provenance_reference"]
        .eq("metadata/external_source_manifest.csv#source_id=odpem_portmore_shelters_2019")
        .all()
    )
    located = frame.loc[frame.geometry.notna()]
    assert located["osm_attribution"].eq("© OpenStreetMap contributors").all()
    assert located["osm_attribution_url"].eq("https://www.openstreetmap.org/copyright").all()


def test_spatial_classification_counts_and_preview_nulls(tmp_path):
    paths, validation, _ = _generated(tmp_path)
    spatial = validation["spatial_classification"]
    assert spatial == {
        "inside_operational_boundary": 11,
        "outside_operational_boundary": 2,
        "in_edge_review_band": 2,
        "in_context_buffer": 11,
        "outside_context_buffer": 2,
        "null_geometry_classifications_unknown": True,
        "classification_semantics": "MVP operational, not legal municipal determination",
    }
    preview = gpd.read_file(paths.preview)
    assert len(preview) == 20
    assert preview.geometry.isna().sum() == 7
