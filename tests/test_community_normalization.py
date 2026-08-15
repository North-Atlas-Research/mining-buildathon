import csv
import json
from pathlib import Path

import geopandas as gpd
from pyproj import CRS

from mining_sprint.community_normalization import (
    CANONICAL_LAYER,
    EXPECTED_INCLUDED_IDS,
    EXPECTED_NAMED_AREAS,
    EXPECTED_TRACE_IDS,
    CommunityPaths,
    community_seed,
    include_source_unit,
    normalize_communities,
    stable_community_id,
)
from mining_sprint.paths import interim_dir, processed_dir, raw_dir


def paths_for(tmp_path: Path) -> CommunityPaths:
    outputs = tmp_path / "Outputs/ws25-005"
    interim = tmp_path / "Interim/communities"
    return CommunityPaths(
        source_archive=raw_dir() / "jamaica.gdb.zip",
        source_workbook=raw_dir() / "jamaica_uscb_202302.xlsx",
        source_metadata_pdf=raw_dir() / "geo-metadata-pgs-uscb-dec16.pdf",
        source_linkage_pdf=raw_dir() / "readme-poplinkagetoshapefile-instructions.pdf",
        boundary=processed_dir() / "region/portmore_boundary.gpkg",
        edge_review=interim_dir() / "region/portmore_boundary_edge_review_750m.gpkg",
        canonical=tmp_path / "Processed/communities/portmore_community_zones_2020.gpkg",
        source_crosswalk=interim / "portmore_source_unit_crosswalk.csv",
        identity_crosswalk=interim / "portmore_community_identity_crosswalk.csv",
        trace_intersections=interim / "portmore_trace_intersections.csv",
        validation=outputs / "validation.json",
        lineage=outputs / "lineage.json",
        preview=outputs / "portmore_community_zones_preview_epsg4326.geojson",
        gap=outputs / "operational_boundary_gap.geojson",
        review_queue=outputs / "review_queue.csv",
    )


def test_uuid_contract_is_deterministic_and_uses_only_source_identity():
    source_id = "JAM_GEO2_14_31"
    first = stable_community_id(source_id)
    assert first == stable_community_id(source_id)
    assert first.startswith("community_")
    assert stable_community_id(source_id) != stable_community_id("JAM_GEO2_14_32")
    assert "WATERFORD" not in community_seed(source_id)
    assert "geometry" not in community_seed(source_id)
    mutable = {"source_id": source_id, "name": "Waterford", "geometry": "first"}
    original = stable_community_id(mutable["source_id"])
    mutable.update(name="Corrected display name", geometry="corrected geometry")
    assert stable_community_id(mutable["source_id"]) == original


def test_portmore_specific_inclusion_threshold_behavior():
    assert include_source_unit(1.0, 100.0)
    assert include_source_unit(28.2, 100.0)
    assert not include_source_unit(0.999999, 100.0)
    assert not include_source_unit(0.0384, 100.0)


def test_canonical_community_artifacts(tmp_path):
    paths = paths_for(tmp_path)
    validation = normalize_communities(paths)
    frame = gpd.read_file(paths.canonical, layer=CANONICAL_LAYER)
    boundary = gpd.read_file(paths.boundary, layer="portmore_jamaica_2020").geometry.iloc[0]

    assert validation["status"] == "passed"
    assert len(frame) == 14
    assert frame.crs == CRS.from_epsg(3448)
    assert frame["community_id"].notna().all() and frame["community_id"].is_unique
    assert frame["source_geography_id"].notna().all()
    assert frame["source_geography_id"].is_unique
    assert set(frame["source_geography_id"]) == EXPECTED_INCLUDED_IDS
    assert frame.geometry.is_valid.all() and not frame.geometry.is_empty.any()
    assert sum(geom.difference(boundary).area for geom in frame.geometry) <= 1e-6
    assert validation["geometry"]["overlap"]["positive_area_pair_count"] == 0
    assert validation["geometry"]["uncovered_area_m2"] > 0
    assert validation["geometry"]["uncovered_percent"] > 0
    assert frame["source_overlap_percent"].ge(1.0).all()
    assert all(
        json.loads(members) == [source_id]
        for members, source_id in zip(
            frame["aggregation_members"], frame["source_geography_id"], strict=True
        )
    )
    assert set(frame["community_name_source"]) >= EXPECTED_NAMED_AREAS
    assert validation["population_firewall"]["population_fields_present"] == []
    assert validation["raw_integrity"]["unchanged"] is True

    with paths.trace_intersections.open(newline="", encoding="utf-8") as source:
        traces = list(csv.DictReader(source))
    assert len(traces) == 4
    assert {row["source_geography_id"] for row in traces} == EXPECTED_TRACE_IDS
    assert all(float(row["source_overlap_percent"]) < 1.0 for row in traces)

    identity = list(csv.DictReader(paths.identity_crosswalk.open(newline="")))
    assert len(identity) == 14
    assert paths.source_crosswalk.exists()
    assert paths.preview.exists() and paths.gap.exists() and paths.lineage.exists()


def test_temporal_and_lineage_contract(tmp_path):
    paths = paths_for(tmp_path)
    validation = normalize_communities(paths)
    lineage = json.loads(paths.lineage.read_text())
    assert validation["temporal_semantics"]["source_geometry_year"] == 2012
    assert (
        "not source geometry vintage"
        in validation["temporal_semantics"]["canonical_filename_year_meaning"]
    )
    assert lineage["source"]["redistribution_status"] == "unresolved_no_rights_claimed"
    assert lineage["population_firewall"]["worldpop_acquired"] is False
    assert lineage["population_firewall"]["population_aggregated"] is False
