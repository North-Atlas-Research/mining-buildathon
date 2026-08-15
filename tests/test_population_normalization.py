from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import geopandas as gpd

from mining_sprint.paths import processed_dir, raw_dir
from mining_sprint.population_normalization import (
    DISTRIBUTION_METHOD,
    PORTMORE_ANCHOR,
    POV_ESTP_TOTAL,
    PROJECTION_METHOD,
    SAINT_CATHERINE_2011,
    SAINT_CATHERINE_2019,
    TARGET_YEAR,
    PopulationPaths,
    normalize_population,
    projected_portmore_population_2020,
)


def paths_for(tmp_path: Path) -> PopulationPaths:
    canonical = tmp_path / "Processed/communities/portmore_community_zones_2020.gpkg"
    canonical.parent.mkdir(parents=True)
    shutil.copy2(processed_dir() / "communities/portmore_community_zones_2020.gpkg", canonical)
    output = tmp_path / "Outputs/ws25-005"
    return PopulationPaths(
        canonical=canonical,
        boundary=processed_dir() / "region/portmore_boundary.gpkg",
        source_archive=raw_dir() / "jamaica.gdb.zip",
        anchor_data=raw_dir() / "410bc3258e7046f6a944e070159f2d38-data.json",
        source_workbook=raw_dir() / "jamaica_uscb_202302.xlsx",
        audit_csv=tmp_path / "Interim/population/portmore_local_2020_population_baseline.csv",
        validation=output / "validation.json",
        lineage=output / "lineage.json",
        preview=output / "community_population_preview_epsg4326.geojson",
        review_queue=output / "review_queue.csv",
    )


def test_approved_projection_formula_is_exact():
    assert PORTMORE_ANCHOR == 182153
    assert SAINT_CATHERINE_2011 == 516218
    assert SAINT_CATHERINE_2019 == 520502
    assert TARGET_YEAR == 2020
    assert projected_portmore_population_2020() == 183854.4916651762


def test_population_attachment_is_complete_deterministic_and_preserves_zones(tmp_path):
    paths = paths_for(tmp_path)
    before = gpd.read_file(paths.canonical, layer="portmore_community_zones_2020")
    first = normalize_population(paths)
    audit_first = paths.audit_csv.read_text(encoding="utf-8")
    second = normalize_population(paths)
    after = gpd.read_file(paths.canonical, layer="portmore_community_zones_2020")
    assert audit_first == paths.audit_csv.read_text(encoding="utf-8")
    assert first["projection"] == second["projection"]
    assert first["canonical"]["record_count"] == 14
    assert first["identity_and_geometry"]["geometry_exactly_unchanged"] is True
    assert list(before.community_id) == list(after.community_id)
    assert list(before.source_geography_id) == list(after.source_geography_id)
    assert all(
        left.equals_exact(right, tolerance=0)
        for left, right in zip(before.geometry, after.geometry, strict=True)
    )
    assert after.crs.to_epsg() == 3448
    assert after.geometry.is_valid.all() and not after.geometry.is_empty.any()
    assert after["pov_estp_2012"].sum() == POV_ESTP_TOTAL
    assert abs(after["population_distribution_weight"].sum() - 1) < 1e-12
    assert (
        abs(after["resident_population_estimate"].sum() - projected_portmore_population_2020())
        < 1e-8
    )
    assert after["population_projection_method"].eq(PROJECTION_METHOD).all()
    assert after["population_distribution_method"].eq(DISTRIBUTION_METHOD).all()
    assert after["population_temporal_uncertainty"].eq("moderate").all()
    assert after["population_spatial_uncertainty"].eq("moderate").all()
    assert after["population_review_required"].all()
    assert not any(column.startswith("worldpop") for column in after.columns)
    assert "resident_population_display_rounded" not in after.columns
    assert paths.preview.exists()
    assert len(list(csv.DictReader(paths.audit_csv.open()))) == 14
    validation = json.loads(paths.validation.read_text(encoding="utf-8"))
    assert validation["worldpop"]["canonical_source_status"] == "rejected_primary_population_source"
    assert validation["population_firewall"]["population_to_demand_conversion"] is False
    assert validation["raw_integrity"]["unchanged"] is True
