"""Normalize the accepted Portmore operational study boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pyogrio
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import transform
from shapely.validation import explain_validity

REGION_ID = "portmore_jamaica_2020"
REGION_NAME = "Portmore 2020 MVP operational study boundary"
SOURCE_IDENTIFIER = "ArcGIS item 410bc3258e7046f6a944e070159f2d38 / Portmore - 02"
SOURCE_ITEM_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/410bc3258e7046f6a944e070159f2d38"
)
SOURCE_DATA_URL = f"{SOURCE_ITEM_URL}/data"
SOURCE_REPRESENTATION_CRS = "ArcGIS wkid 102100 / EPSG:3857"
ORIGINAL_SOURCE_CRS = "unknown"
CANONICAL_STORAGE_CRS = "EPSG:3448"
ANALYSIS_CRS = "EPSG:3448"
SOURCE_PROVENANCE_REFERENCE = (
    "metadata/raw_manifest.csv#relative_path=410bc3258e7046f6a944e070159f2d38-data.json"
)
BOUNDARY_ROLE = "operational_study_boundary"
LEGAL_AUTHORITY_FLAG = False
LEGAL_BOUNDARY_CAVEAT = (
    "The operational study boundary is a practical digital representation for the MVP and "
    "has not been demonstrated to reproduce the statutory Portmore boundary exactly."
)
VALIDATION_SOURCE = "Census / STATIN-derived JAM_GEO1_14_02"
KNOWN_BOUNDARY_UNCERTAINTY = (
    "Localized ArcGIS/Census differences exceed 100 m; WS25-002A found the largest differences "
    "near Waterford and Edgewater, without a georeferenced legal-map adjudication."
)
BOUNDARY_EDGE_REVIEW_DISTANCE_M = 750
ACQUISITION_CONTEXT_BUFFER_M = 2000
LAYER_NAME = REGION_ID
EXPECTED_WS25_002_AREA_M2 = 182_075_635.40073112
EXPECTED_WS25_002_PERIMETER_M = 95_243.0400573416
AREA_TOLERANCE_M2 = 1.0
PERIMETER_TOLERANCE_M = 0.01
ROUND_TRIP_HAUSDORFF_TOLERANCE_M = 1e-5


class RegionNormalizationError(RuntimeError):
    """Raised when normalization cannot proceed without changing the accepted geometry."""


@dataclass(frozen=True)
class RegionPaths:
    """Input and output locations for the normalization workflow."""

    item_metadata: Path
    item_data: Path
    census_archive: Path
    canonical: Path
    edge_review: Path
    context_buffer: Path
    preview: Path
    validation: Path
    lineage: Path


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def extract_accepted_portmore(item_data_path: Path) -> tuple[Polygon, dict[str, object]]:
    """Extract the single frozen Portmore feature from the original ArcGIS response bytes."""
    payload = json.loads(item_data_path.read_bytes())
    matches = []
    for index, operational_layer in enumerate(payload.get("operationalLayers", [])):
        for sublayer in operational_layer.get("featureCollection", {}).get("layers", []):
            for feature in sublayer.get("featureSet", {}).get("features", []):
                attributes = feature.get("attributes", {})
                if (
                    attributes.get("NAME") == "Portmore"
                    and operational_layer.get("title") == "Portmore - 02"
                ):
                    matches.append((index, operational_layer, sublayer, feature))
    if len(matches) != 1:
        raise RegionNormalizationError(
            f"Accepted Portmore feature must have one exact match; found {len(matches)}"
        )
    index, operational_layer, sublayer, feature = matches[0]
    geometry_payload = feature.get("geometry", {})
    if geometry_payload.get("spatialReference") != {"wkid": 102100}:
        raise RegionNormalizationError(
            "Accepted feature does not declare ArcGIS representation CRS wkid 102100"
        )
    rings = geometry_payload.get("rings", [])
    if len(rings) != 1:
        raise RegionNormalizationError(
            f"Accepted feature must contain one ring; found {len(rings)}"
        )
    geometry = Polygon(rings[0])
    require_valid_non_empty(geometry, "accepted ArcGIS source geometry")
    evidence = {
        "operational_layer_index": index,
        "operational_layer_id": operational_layer.get("id"),
        "operational_layer_title": operational_layer.get("title"),
        "layer_geometry_type": sublayer.get("layerDefinition", {}).get("geometryType"),
        "attributes": feature.get("attributes", {}),
        "ring_count": len(rings),
        "coordinate_count": sum(len(ring) for ring in rings),
        "declared_spatial_reference": geometry_payload.get("spatialReference"),
    }
    return geometry, evidence


def require_valid_non_empty(geometry, label: str) -> None:
    """Stop instead of silently repairing an invalid or empty geometry."""
    if geometry.is_empty:
        raise RegionNormalizationError(f"{label} is empty; no repair was attempted")
    if not geometry.is_valid:
        raise RegionNormalizationError(
            f"{label} is invalid: {explain_validity(geometry)}; no repair was attempted"
        )


def transform_geometry(geometry, source_crs: int | str, target_crs: int | str):
    """Transform without rounding, simplification, snapping, or repair."""
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    transformed = transform(transformer.transform, geometry)
    require_valid_non_empty(transformed, f"geometry transformed to {target_crs}")
    return transformed


def canonical_attributes() -> dict[str, object]:
    """Return the frozen canonical region attributes."""
    return {
        "region_id": REGION_ID,
        "region_name": REGION_NAME,
        "source_identifier": SOURCE_IDENTIFIER,
        "source_representation_crs": SOURCE_REPRESENTATION_CRS,
        "original_source_crs": ORIGINAL_SOURCE_CRS,
        "canonical_storage_crs": CANONICAL_STORAGE_CRS,
        "analysis_crs": ANALYSIS_CRS,
        "source_provenance_reference": SOURCE_PROVENANCE_REFERENCE,
        "boundary_role": BOUNDARY_ROLE,
        "legal_authority_flag": LEGAL_AUTHORITY_FLAG,
        "legal_boundary_caveat": LEGAL_BOUNDARY_CAVEAT,
        "validation_source": VALIDATION_SOURCE,
        "known_boundary_uncertainty": KNOWN_BOUNDARY_UNCERTAINTY,
        "boundary_edge_review_distance_m": BOUNDARY_EDGE_REVIEW_DISTANCE_M,
        "acquisition_context_buffer_m": ACQUISITION_CONTEXT_BUFFER_M,
    }


def write_geopackage(path: Path, layer: str, geometry, attributes: dict[str, object]) -> None:
    """Write one canonical or derived EPSG:3448 feature."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = gpd.GeoDataFrame([attributes], geometry=[geometry], crs=ANALYSIS_CRS)
    frame.to_file(path, layer=layer, driver="GPKG", index=False)


def epsg_3448_checks(geometry_3448) -> dict[str, object]:
    """Verify that EPSG:3448 is projected, metric, and applicable to Portmore."""
    crs = CRS.from_epsg(3448)
    units = sorted({axis.unit_name for axis in crs.axis_info})
    centroid_4326 = transform(
        Transformer.from_crs(3448, 4326, always_xy=True).transform,
        geometry_3448.centroid,
    )
    area = crs.area_of_use
    covers_centroid = (
        area.west <= centroid_4326.x <= area.east and area.south <= centroid_4326.y <= area.north
    )
    if not crs.is_projected or units != ["metre"] or not covers_centroid:
        raise RegionNormalizationError(
            "EPSG:3448 failed projected/metric/Portmore area-of-use validation"
        )
    return {
        "name": crs.name,
        "is_projected": crs.is_projected,
        "axis_units": units,
        "area_of_use": {
            "name": area.name,
            "bounds_wgs84": [area.west, area.south, area.east, area.north],
        },
        "canonical_centroid_wgs84": [centroid_4326.x, centroid_4326.y],
        "area_of_use_covers_centroid": covers_centroid,
    }


def named_area_checks(canonical_geometry, census_archive: Path) -> list[dict[str, object]]:
    """Check the frozen named-area list using Census solely as validation geometry."""
    communities = gpd.read_file(
        f"/vsizip/{census_archive}", layer="JM_GEOG2_ADM2_2012_uscb_202302"
    ).to_crs(ANALYSIS_CRS)
    results = []
    for name in [
        "GREGORY PARK",
        "WATERFORD",
        "EDGEWATER",
        "GREATER PORTMORE",
        "PASSAGE FORT",
        "BRAETON",
        "CROMARTY",
    ]:
        matches = communities.loc[communities["AREA_NAME"] == name]
        if len(matches) != 1:
            raise RegionNormalizationError(
                f"Validation area {name!r} must have one exact match; found {len(matches)}"
            )
        row = matches.iloc[0]
        representative = row.geometry.representative_point()
        results.append(
            {
                "name": name.title(),
                "source_identifier": row["GEO_MATCH"],
                "representative_point_inside": canonical_geometry.covers(representative),
                "intersection_percent": 100
                * canonical_geometry.intersection(row.geometry).area
                / row.geometry.area,
                "boundary_intersects": row.geometry.intersects(canonical_geometry.boundary),
            }
        )
    if not all(result["representative_point_inside"] for result in results):
        raise RegionNormalizationError(
            "One or more named validation areas failed inclusion sanity check"
        )
    return results


def normalize_region(paths: RegionPaths) -> dict[str, object]:
    """Generate and validate the canonical boundary and reproducible derivatives."""
    raw_before = {
        str(path): {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in [paths.item_metadata, paths.item_data, paths.census_archive]
    }
    source_geometry, source_evidence = extract_accepted_portmore(paths.item_data)
    canonical_geometry = transform_geometry(source_geometry, 3857, 3448)
    require_valid_non_empty(canonical_geometry, "canonical geometry")

    edge_review = canonical_geometry.boundary.buffer(BOUNDARY_EDGE_REVIEW_DISTANCE_M)
    context_buffer = canonical_geometry.buffer(ACQUISITION_CONTEXT_BUFFER_M)
    require_valid_non_empty(edge_review, "750 m boundary-edge review geometry")
    require_valid_non_empty(context_buffer, "2,000 m acquisition/context buffer")
    if not edge_review.equals_exact(
        canonical_geometry.boundary.buffer(BOUNDARY_EDGE_REVIEW_DISTANCE_M), 0
    ) or not context_buffer.equals_exact(
        canonical_geometry.buffer(ACQUISITION_CONTEXT_BUFFER_M), 0
    ):
        raise RegionNormalizationError("Derived buffer geometry is not reproducible")

    write_geopackage(paths.canonical, LAYER_NAME, canonical_geometry, canonical_attributes())
    write_geopackage(
        paths.edge_review,
        "portmore_boundary_edge_review_750m",
        edge_review,
        {
            "region_id": REGION_ID,
            "distance_m": BOUNDARY_EDGE_REVIEW_DISTANCE_M,
            "derivation": "canonical_boundary.boundary.buffer(750)",
        },
    )
    write_geopackage(
        paths.context_buffer,
        "portmore_acquisition_context_buffer_2000m",
        context_buffer,
        {
            "region_id": REGION_ID,
            "distance_m": ACQUISITION_CONTEXT_BUFFER_M,
            "derivation": "canonical_boundary.buffer(2000)",
        },
    )

    stored = gpd.read_file(paths.canonical, layer=LAYER_NAME)
    if len(stored) != 1 or stored.crs != CRS.from_epsg(3448):
        raise RegionNormalizationError("Canonical GeoPackage feature count or CRS is inconsistent")
    stored_geometry = stored.geometry.iloc[0]
    require_valid_non_empty(stored_geometry, "stored canonical geometry")
    storage_equals_exact = stored_geometry.equals_exact(canonical_geometry, 0)
    storage_symmetric_difference_m2 = stored_geometry.symmetric_difference(canonical_geometry).area
    if not storage_equals_exact or storage_symmetric_difference_m2 != 0:
        raise RegionNormalizationError("GeoPackage storage changed canonical geometry coordinates")

    round_trip = transform_geometry(canonical_geometry, 3448, 3857)
    round_trip_hausdorff_m = source_geometry.hausdorff_distance(round_trip)
    round_trip_symmetric_difference_m2 = source_geometry.symmetric_difference(round_trip).area
    if round_trip_hausdorff_m > ROUND_TRIP_HAUSDORFF_TOLERANCE_M:
        raise RegionNormalizationError(
            f"CRS round trip exceeds tolerance: {round_trip_hausdorff_m} m"
        )

    area_difference_m2 = canonical_geometry.area - EXPECTED_WS25_002_AREA_M2
    perimeter_difference_m = canonical_geometry.length - EXPECTED_WS25_002_PERIMETER_M
    if (
        abs(area_difference_m2) > AREA_TOLERANCE_M2
        or abs(perimeter_difference_m) > PERIMETER_TOLERANCE_M
    ):
        raise RegionNormalizationError("Canonical metrics are inconsistent with WS25-002")

    paths.preview.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(
        [canonical_attributes()], geometry=[canonical_geometry], crs=ANALYSIS_CRS
    ).to_crs(4326).to_file(paths.preview, driver="GeoJSON", index=False)

    raw_after = {
        str(path): {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in [paths.item_metadata, paths.item_data, paths.census_archive]
    }
    raw_unchanged = raw_before == raw_after
    if not raw_unchanged:
        raise RegionNormalizationError("Raw input size or SHA-256 changed during normalization")

    validation = {
        "status": "passed",
        "region_id": REGION_ID,
        "canonical_path": str(paths.canonical),
        "canonical_layer": LAYER_NAME,
        "source_geometry": {
            "geometry_type": source_geometry.geom_type,
            "valid": source_geometry.is_valid,
            "empty": source_geometry.is_empty,
            "bounds_epsg3857": list(source_geometry.bounds),
        },
        "canonical_geometry": {
            "geometry_type": stored_geometry.geom_type,
            "valid": stored_geometry.is_valid,
            "empty": stored_geometry.is_empty,
            "bounds_epsg3448": list(stored_geometry.bounds),
            "area_m2": stored_geometry.area,
            "perimeter_m": stored_geometry.length,
        },
        "geometry_equivalence": {
            "stored_equals_transformed_source_exact": storage_equals_exact,
            "stored_symmetric_difference_m2": storage_symmetric_difference_m2,
            "round_trip_hausdorff_m_in_epsg3857": round_trip_hausdorff_m,
            "round_trip_symmetric_difference_m2_in_epsg3857": (round_trip_symmetric_difference_m2),
            "round_trip_hausdorff_tolerance_m": ROUND_TRIP_HAUSDORFF_TOLERANCE_M,
        },
        "ws25_002_metric_consistency": {
            "expected_area_m2": EXPECTED_WS25_002_AREA_M2,
            "actual_area_m2": stored_geometry.area,
            "difference_m2": area_difference_m2,
            "area_tolerance_m2": AREA_TOLERANCE_M2,
            "expected_perimeter_m": EXPECTED_WS25_002_PERIMETER_M,
            "actual_perimeter_m": stored_geometry.length,
            "difference_m": perimeter_difference_m,
            "perimeter_tolerance_m": PERIMETER_TOLERANCE_M,
            "tolerance_justification": (
                "Allows sub-metre numerical variation across PROJ/GDAL builds while being far "
                "below the 750 m review distance; current build reproduces the values exactly."
            ),
        },
        "epsg_3448": epsg_3448_checks(stored_geometry),
        "derived_geometries": {
            "edge_review": {
                "path": str(paths.edge_review),
                "definition": "canonical_boundary.boundary.buffer(750)",
                "valid": edge_review.is_valid,
                "geometry_type": edge_review.geom_type,
                "area_m2": edge_review.area,
                "perimeter_m": edge_review.length,
                "bounds_epsg3448": list(edge_review.bounds),
            },
            "context_buffer": {
                "path": str(paths.context_buffer),
                "definition": "canonical_boundary.buffer(2000)",
                "valid": context_buffer.is_valid,
                "geometry_type": context_buffer.geom_type,
                "area_m2": context_buffer.area,
                "perimeter_m": context_buffer.length,
                "bounds_epsg3448": list(context_buffer.bounds),
            },
        },
        "named_area_checks": named_area_checks(stored_geometry, paths.census_archive),
        "raw_integrity": {"unchanged": raw_unchanged, "inputs": raw_after},
    }
    paths.validation.parent.mkdir(parents=True, exist_ok=True)
    paths.validation.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")

    item_metadata = json.loads(paths.item_metadata.read_bytes())
    lineage = {
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "region_id": REGION_ID,
        "source": {
            "item_id": item_metadata.get("id"),
            "owner": item_metadata.get("owner"),
            "title": item_metadata.get("title"),
            "item_type": item_metadata.get("type"),
            "item_access": item_metadata.get("access"),
            "license_info": item_metadata.get("licenseInfo"),
            "item_metadata_url": SOURCE_ITEM_URL,
            "item_data_url": SOURCE_DATA_URL,
            "licensing_note": (
                "Public access does not establish permission for redistribution or publication "
                "of source-derived geometry."
            ),
            "source_representation_crs": SOURCE_REPRESENTATION_CRS,
            "original_source_crs": ORIGINAL_SOURCE_CRS,
            "provenance_reference": SOURCE_PROVENANCE_REFERENCE,
            "feature_evidence": source_evidence,
            "raw_inputs": raw_after,
        },
        "transformation": {
            "operation": "EPSG:3857 to EPSG:3448 with pyproj Transformer(always_xy=True)",
            "geometry_changes": [
                "coordinate transformation only",
                "no rounding",
                "no simplification",
                "no snapping",
                "no dissolve",
                "no repair",
            ],
            "canonical_geometry_type": stored_geometry.geom_type,
        },
        "derivatives": {
            "canonical": {"path": str(paths.canonical), "sha256": sha256(paths.canonical)},
            "edge_review": {"path": str(paths.edge_review), "sha256": sha256(paths.edge_review)},
            "context_buffer": {
                "path": str(paths.context_buffer),
                "sha256": sha256(paths.context_buffer),
            },
            "preview": {"path": str(paths.preview), "sha256": sha256(paths.preview)},
            "validation": {
                "path": str(paths.validation),
                "sha256": sha256(paths.validation),
            },
        },
        "software": {
            "geopandas": gpd.__version__,
            "pyogrio": pyogrio.__version__,
            "shapely": shapely.__version__,
        },
    }
    paths.lineage.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    return validation
