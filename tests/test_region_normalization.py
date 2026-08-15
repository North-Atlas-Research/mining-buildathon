from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from mining_sprint.region_normalization import (
    ANALYSIS_CRS,
    BOUNDARY_EDGE_REVIEW_DISTANCE_M,
    LAYER_NAME,
    REGION_ID,
    RegionNormalizationError,
    canonical_attributes,
    extract_accepted_portmore,
    require_valid_non_empty,
    transform_geometry,
    write_geopackage,
)


def write_arcgis_payload(path: Path, rings, *, title: str = "Portmore - 02") -> None:
    payload = {
        "operationalLayers": [
            {
                "id": "accepted-layer-id",
                "title": title,
                "featureCollection": {
                    "layers": [
                        {
                            "layerDefinition": {"geometryType": "esriGeometryPolygon"},
                            "featureSet": {
                                "features": [
                                    {
                                        "attributes": {"NAME": "Portmore"},
                                        "geometry": {
                                            "rings": rings,
                                            "spatialReference": {"wkid": 102100},
                                        },
                                    }
                                ]
                            },
                        }
                    ]
                },
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_extracts_only_frozen_feature_and_preserves_coordinates(tmp_path):
    source = tmp_path / "item-data.json"
    ring = [
        [-8576000.125, 2019000.25],
        [-8575000.5, 2019000.25],
        [-8575000.5, 2020000.75],
        [-8576000.125, 2019000.25],
    ]
    write_arcgis_payload(source, [ring])
    geometry, evidence = extract_accepted_portmore(source)
    assert list(geometry.exterior.coords) == [tuple(coordinate) for coordinate in ring]
    assert evidence["operational_layer_id"] == "accepted-layer-id"
    assert evidence["coordinate_count"] == 4


def test_rejects_wrong_feature(tmp_path):
    source = tmp_path / "item-data.json"
    write_arcgis_payload(source, [[[0, 0], [1, 0], [1, 1], [0, 0]]], title="Different")
    with pytest.raises(RegionNormalizationError, match="one exact match; found 0"):
        extract_accepted_portmore(source)


def test_invalid_source_stops_without_repair(tmp_path):
    source = tmp_path / "item-data.json"
    bowtie = [[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]
    write_arcgis_payload(source, [bowtie])
    with pytest.raises(RegionNormalizationError, match="invalid.*no repair was attempted"):
        extract_accepted_portmore(source)


def test_transform_round_trip_is_numerically_equivalent():
    source = Polygon(
        [
            (-8576000.125, 2019000.25),
            (-8575000.5, 2019000.25),
            (-8575000.5, 2020000.75),
            (-8576000.125, 2019000.25),
        ]
    )
    canonical = transform_geometry(source, 3857, 3448)
    round_trip = transform_geometry(canonical, 3448, 3857)
    assert canonical.is_valid and not canonical.is_empty
    assert source.hausdorff_distance(round_trip) < 1e-5


def test_canonical_attributes_include_frozen_schema():
    attributes = canonical_attributes()
    assert attributes["region_id"] == REGION_ID
    assert attributes["analysis_crs"] == ANALYSIS_CRS
    assert attributes["legal_authority_flag"] is False
    assert attributes["boundary_edge_review_distance_m"] == BOUNDARY_EDGE_REVIEW_DISTANCE_M
    assert "statutory Portmore boundary exactly" in attributes["legal_boundary_caveat"]


def test_geopackage_round_trip_preserves_geometry_and_schema(tmp_path):
    path = tmp_path / "portmore_boundary.gpkg"
    geometry = Polygon(
        [
            (745000.125, 632000.25),
            (746000.5, 632000.25),
            (746000.5, 633000.75),
            (745000.125, 632000.25),
        ]
    )
    write_geopackage(path, LAYER_NAME, geometry, canonical_attributes())
    stored = gpd.read_file(path, layer=LAYER_NAME)
    assert len(stored) == 1
    assert stored.crs.to_epsg() == 3448
    assert stored.geometry.iloc[0].equals_exact(geometry, 0)
    assert set(canonical_attributes()).issubset(stored.columns)
    assert stored.iloc[0]["region_id"] == REGION_ID


def test_empty_geometry_stops_without_repair():
    with pytest.raises(RegionNormalizationError, match="empty.*no repair was attempted"):
        require_valid_non_empty(Polygon(), "test geometry")
