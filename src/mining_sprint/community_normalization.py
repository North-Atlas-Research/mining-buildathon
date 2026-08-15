"""Build canonical Portmore planning zones from documented community geography."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pyogrio
import shapely
from pyproj import CRS
from shapely.validation import explain_validity

from mining_sprint.region_normalization import sha256

SOURCE_LAYER = "JM_GEOG2_ADM2_2012_uscb_202302"
SOURCE_GEOMETRY_YEAR = 2012
SOURCE_ID_FIELD = "GEO_MATCH"
SOURCE_NAME_FIELD = "AREA_NAME"
CANONICAL_LAYER = "portmore_community_zones_2020"
CANONICAL_CRS = "EPSG:3448"
ZONE_ROLE = "mvp_operational_planning_zone"
CONSTRUCTION_METHOD = "source_community_clipped_to_operational_boundary"
INCLUSION_THRESHOLD = 0.01
UUID_NAMESPACE = uuid.UUID("0d710476-d218-52c0-aeb1-c3bcd144f704")
UUID_NAMESPACE_DERIVATION = (
    "UUIDv5(NAMESPACE_URL, "
    "https://github.com/North-Atlas-Research/mining-sprint/ws25-005/community-zones)"
)
UUID_SEED_TEMPLATE = "ws25-005|JM_GEOG2_ADM2_2012_uscb_202302|<GEO_MATCH>|direct_source_clipped_v1"
SOURCE_PROVENANCE_REFERENCE = (
    "metadata/raw_manifest.csv#relative_path=jamaica.gdb.zip; jamaica_uscb_202302.xlsx#Metadata"
)
SOURCE_CHECKSUM_SHA256 = "3b238b5618247f5dd98d2daaecc5442026f233779e3e823659bce6a35350603f"
LICENSING_STATUS = "unresolved_no_rights_claimed"
EXPECTED_INCLUDED_IDS = {
    "JAM_GEO2_14_54",
    "JAM_GEO2_14_49",
    "JAM_GEO2_14_40",
    "JAM_GEO2_14_42",
    "JAM_GEO2_14_41",
    "JAM_GEO2_14_31",
    "JAM_GEO2_14_32",
    "JAM_GEO2_14_37",
    "JAM_GEO2_14_39",
    "JAM_GEO2_14_38",
    "JAM_GEO2_14_35",
    "JAM_GEO2_14_34",
    "JAM_GEO2_14_36",
    "JAM_GEO2_14_33",
}
EXPECTED_TRACE_IDS = {
    "JAM_GEO2_02_22",
    "JAM_GEO2_14_30",
    "JAM_GEO2_14_53",
    "JAM_GEO2_14_23",
}
EXPECTED_NAMED_AREAS = {
    "GREGORY PARK",
    "WATERFORD",
    "EDGEWATER",
    "GREATER PORTMORE",
    "PASSAGE FORT",
    "BRAETON",
    "CROMARTY",
}


class CommunityNormalizationError(RuntimeError):
    """Raised when approved source or geometry contracts are violated."""


@dataclass(frozen=True)
class CommunityPaths:
    """Input and output paths for WS25-005 community normalization."""

    source_archive: Path
    source_workbook: Path
    source_metadata_pdf: Path
    source_linkage_pdf: Path
    boundary: Path
    edge_review: Path
    canonical: Path
    source_crosswalk: Path
    identity_crosswalk: Path
    trace_intersections: Path
    validation: Path
    lineage: Path
    preview: Path
    gap: Path
    review_queue: Path


def community_seed(source_geography_id: str) -> str:
    """Return the exact immutable UUIDv5 seed for a source unit."""
    return f"ws25-005|{SOURCE_LAYER}|{source_geography_id}|direct_source_clipped_v1"


def stable_community_id(source_geography_id: str) -> str:
    """Return a stable ID independent of names, geometry, population, and row order."""
    return f"community_{uuid.uuid5(UUID_NAMESPACE, community_seed(source_geography_id))}"


def include_source_unit(intersection_area_m2: float, source_full_area_m2: float) -> bool:
    """Apply the approved Portmore-specific source-area overlap rule."""
    if source_full_area_m2 <= 0:
        raise CommunityNormalizationError("Source full area must be positive")
    return intersection_area_m2 / source_full_area_m2 >= INCLUSION_THRESHOLD


def normalize_name(value: str) -> str:
    """Return a deterministic lowercase ASCII search key without changing source text."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def display_name(value: str) -> str:
    """Return a human-facing title while retaining the source name separately."""
    return value.title()


def require_valid_non_empty(geometry, label: str) -> None:
    """Stop rather than silently repairing invalid or empty geometry."""
    if geometry.is_empty:
        raise CommunityNormalizationError(f"{label} is empty; no repair attempted")
    if not geometry.is_valid:
        raise CommunityNormalizationError(
            f"{label} is invalid: {explain_validity(geometry)}; no repair attempted"
        )


def _read_single_geometry(path: Path, layer: str):
    frame = gpd.read_file(path, layer=layer)
    if len(frame) != 1 or frame.crs != CRS.from_epsg(3448):
        raise CommunityNormalizationError(f"Unexpected layer count or CRS: {path}:{layer}")
    geometry = frame.geometry.iloc[0]
    require_valid_non_empty(geometry, f"{path}:{layer}")
    return geometry


def _raw_state(paths: CommunityPaths) -> dict[str, dict[str, object]]:
    return {
        path.name: {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in [
            paths.source_archive,
            paths.source_workbook,
            paths.source_metadata_pdf,
            paths.source_linkage_pdf,
        ]
    }


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _overlap_metrics(frame: gpd.GeoDataFrame) -> dict[str, object]:
    count = 0
    total = 0.0
    maximum = 0.0
    for left in range(len(frame)):
        for right in range(left + 1, len(frame)):
            area = frame.geometry.iloc[left].intersection(frame.geometry.iloc[right]).area
            if area > 1e-6:
                count += 1
                total += area
                maximum = max(maximum, area)
    return {
        "positive_area_pair_count": count,
        "total_overlap_area_m2": total,
        "maximum_pairwise_overlap_area_m2": maximum,
        "positive_area_tolerance_m2": 1e-6,
    }


def normalize_communities(paths: CommunityPaths) -> dict[str, object]:
    """Generate, validate, and document the approved 14-zone construction."""
    raw_before = _raw_state(paths)
    if raw_before[paths.source_archive.name]["sha256"] != SOURCE_CHECKSUM_SHA256:
        raise CommunityNormalizationError("Source archive checksum does not match contract")

    source_path = f"/vsizip/{paths.source_archive}/Jamaica.gdb"
    layers = {name for name, _ in pyogrio.list_layers(source_path)}
    if SOURCE_LAYER not in layers:
        raise CommunityNormalizationError(f"Required source layer absent: {SOURCE_LAYER}")
    source = gpd.read_file(source_path, layer=SOURCE_LAYER).to_crs(CANONICAL_CRS)
    if source.crs != CRS.from_epsg(3448):
        raise CommunityNormalizationError("Source transformation to EPSG:3448 failed")
    if source[SOURCE_ID_FIELD].isna().any() or source[SOURCE_ID_FIELD].duplicated().any():
        raise CommunityNormalizationError("Source geography identifiers are null or duplicate")
    if (~source.geometry.is_valid).any() or source.geometry.is_empty.any():
        raise CommunityNormalizationError("Source layer has invalid or empty geometry")

    boundary = _read_single_geometry(paths.boundary, "portmore_jamaica_2020")
    edge = _read_single_geometry(paths.edge_review, "portmore_boundary_edge_review_750m")
    source["source_full_area_m2"] = source.geometry.area
    source["intersection_area_m2"] = source.geometry.intersection(boundary).area
    intersections = source.loc[source["intersection_area_m2"] > 0].copy()
    intersections["source_overlap_ratio"] = (
        intersections["intersection_area_m2"] / intersections["source_full_area_m2"]
    )
    intersections["source_overlap_percent"] = 100 * intersections["source_overlap_ratio"]
    intersections["included"] = [
        include_source_unit(intersection, full)
        for intersection, full in zip(
            intersections["intersection_area_m2"],
            intersections["source_full_area_m2"],
            strict=True,
        )
    ]
    included = intersections.loc[intersections["included"]].copy()
    traces = intersections.loc[~intersections["included"]].copy()

    included_ids = set(included[SOURCE_ID_FIELD])
    trace_ids = set(traces[SOURCE_ID_FIELD])
    if included_ids != EXPECTED_INCLUDED_IDS or len(included) != 14:
        raise CommunityNormalizationError(
            f"Included source IDs differ from approved 14: {sorted(included_ids)}"
        )
    if trace_ids != EXPECTED_TRACE_IDS:
        raise CommunityNormalizationError(
            f"Trace source IDs differ from approved set: {sorted(trace_ids)}"
        )

    recorded = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    canonical_rows: list[dict[str, object]] = []
    canonical_geometries = []
    source_crosswalk_rows: list[dict[str, object]] = []
    identity_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []

    for row in intersections.sort_values(SOURCE_ID_FIELD).itertuples():
        source_id = getattr(row, SOURCE_ID_FIELD)
        source_name = getattr(row, SOURCE_NAME_FIELD)
        included_flag = bool(row.included)
        source_crosswalk_rows.append(
            {
                "source_geography_id": source_id,
                "source_geography_name": source_name,
                "source_full_area_m2": row.source_full_area_m2,
                "intersection_area_m2": row.intersection_area_m2,
                "source_overlap_percent": row.source_overlap_percent,
                "inclusion_threshold": INCLUSION_THRESHOLD,
                "included_in_canonical": str(included_flag).lower(),
                "decision": "included_substantive_intersection"
                if included_flag
                else "excluded_trace_intersection",
            }
        )
        if not included_flag:
            review_rows.append(
                {
                    "community_id": "",
                    "source_geography_id": source_id,
                    "source_geography_name": source_name,
                    "review_category": "trace_intersection",
                    "review_status": "required",
                    "review_note": "Positive-area intersection below the approved Portmore-specific 1% source-area threshold",
                }
            )
            continue

        geometry = row.geometry.intersection(boundary)
        require_valid_non_empty(geometry, f"clipped geometry for {source_id}")
        outside_area = row.geometry.difference(boundary).area
        crosses = row.intersection_area_m2 > 0 and outside_area > 1e-6
        edge_required = geometry.intersects(edge)
        community_id = stable_community_id(source_id)
        canonical_rows.append(
            {
                "community_id": community_id,
                "community_name": display_name(source_name),
                "community_name_source": source_name,
                "community_name_normalized": normalize_name(source_name),
                "zone_role": ZONE_ROLE,
                "source_geography_id": source_id,
                "source_geography_name": source_name,
                "source_provenance_reference": SOURCE_PROVENANCE_REFERENCE,
                "source_checksum_sha256": SOURCE_CHECKSUM_SHA256,
                "source_redistribution_status": LICENSING_STATUS,
                "zone_construction_method": CONSTRUCTION_METHOD,
                "aggregation_members": json.dumps([source_id], separators=(",", ":")),
                "source_geometry_year": SOURCE_GEOMETRY_YEAR,
                "source_geometry_year_semantics": "STATIN-reported community geography vintage; not a 2020 survey date",
                "source_full_area_m2": row.source_full_area_m2,
                "canonical_clipped_area_m2": geometry.area,
                "source_overlap_percent": row.source_overlap_percent,
                "inside_operational_boundary": geometry.difference(boundary).area <= 1e-6,
                "crosses_operational_boundary": crosses,
                "boundary_edge_review_required": edge_required,
                "canonical_storage_crs": CANONICAL_CRS,
                "analysis_crs": CANONICAL_CRS,
                "valid_time": "2012",
                "recorded_time": recorded,
                "known_uncertainty": "2012-era source community geography; USCB does not guarantee positional accuracy; redistribution rights unresolved; clipped to an MVP operational boundary that is not statutory",
            }
        )
        canonical_geometries.append(geometry)
        identity_rows.append(
            {
                "community_id": community_id,
                "source_geography_id": source_id,
                "source_geography_name": source_name,
                "community_name": display_name(source_name),
                "community_name_normalized": normalize_name(source_name),
                "alias": "",
                "alias_source": "",
                "identity_review_required": "false",
                "identity_notes": "One-to-one source identity; no alias invented",
            }
        )
        if crosses:
            review_rows.append(
                {
                    "community_id": community_id,
                    "source_geography_id": source_id,
                    "source_geography_name": source_name,
                    "review_category": "boundary_crossing",
                    "review_status": "required",
                    "review_note": "Original source unit crosses the operational boundary; canonical geometry is clipped",
                }
            )
        if edge_required:
            review_rows.append(
                {
                    "community_id": community_id,
                    "source_geography_id": source_id,
                    "source_geography_name": source_name,
                    "review_category": "boundary_edge",
                    "review_status": "required",
                    "review_note": "Canonical geometry intersects the established two-sided 750 m boundary-edge review band",
                }
            )
        if source_name in {"HELLSHIRE", "CROMARTY"}:
            review_rows.append(
                {
                    "community_id": community_id,
                    "source_geography_id": source_id,
                    "source_geography_name": source_name,
                    "review_category": "large_heterogeneous_zone",
                    "review_status": "required",
                    "review_note": "Large source community may contain substantial non-residential or heterogeneous geography; no unsupported subdivision performed",
                }
            )
        review_rows.append(
            {
                "community_id": community_id,
                "source_geography_id": source_id,
                "source_geography_name": source_name,
                "review_category": "source_licensing",
                "review_status": "required",
                "review_note": "Redistribution/licensing terms remain unresolved; no permissive rights claimed",
            }
        )

    canonical = gpd.GeoDataFrame(canonical_rows, geometry=canonical_geometries, crs=CANONICAL_CRS)
    if len(canonical) != 14:
        raise CommunityNormalizationError(f"Expected 14 canonical zones; found {len(canonical)}")
    if canonical["community_id"].isna().any() or canonical["community_id"].duplicated().any():
        raise CommunityNormalizationError("Canonical community IDs are null or duplicate")
    if canonical["source_geography_id"].duplicated().any():
        raise CommunityNormalizationError("Canonical source IDs are duplicate")
    if (~canonical.geometry.is_valid).any() or canonical.geometry.is_empty.any():
        raise CommunityNormalizationError("Canonical geometry validity failed")
    outside_m2 = float(canonical.geometry.map(lambda geom: geom.difference(boundary).area).sum())
    if outside_m2 > 1e-6:
        raise CommunityNormalizationError(f"Canonical geometry outside boundary: {outside_m2} m2")

    overlap = _overlap_metrics(canonical)
    if overlap["positive_area_pair_count"] != 0:
        raise CommunityNormalizationError(f"Canonical zones overlap: {overlap}")
    union = canonical.geometry.union_all()
    require_valid_non_empty(union, "canonical zone union")
    gap = boundary.difference(union)
    require_valid_non_empty(gap, "operational boundary gap")
    trace_union = traces.geometry.intersection(boundary).union_all()
    trace_gap_area = gap.intersection(trace_union).area

    for row in canonical.itertuples():
        if row.geometry.boundary.intersects(gap.boundary):
            review_rows.append(
                {
                    "community_id": row.community_id,
                    "source_geography_id": row.source_geography_id,
                    "source_geography_name": row.source_geography_name,
                    "review_category": "gap_adjacent",
                    "review_status": "required",
                    "review_note": "Canonical zone is adjacent to explicit uncovered operational-boundary gap; gap was not assigned",
                }
            )

    paths.canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_file(paths.canonical, layer=CANONICAL_LAYER, driver="GPKG", index=False)
    stored = gpd.read_file(paths.canonical, layer=CANONICAL_LAYER)
    if len(stored) != 14 or stored.crs != CRS.from_epsg(3448):
        raise CommunityNormalizationError("Stored canonical count or CRS changed")
    if (~stored.geometry.is_valid).any() or stored.geometry.is_empty.any():
        raise CommunityNormalizationError("Stored canonical geometry invalid or empty")

    _write_csv(
        paths.source_crosswalk,
        source_crosswalk_rows,
        list(source_crosswalk_rows[0]),
    )
    _write_csv(paths.identity_crosswalk, identity_rows, list(identity_rows[0]))
    trace_rows = [row for row in source_crosswalk_rows if row["included_in_canonical"] == "false"]
    for row in trace_rows:
        row["exclusion_reason"] = "source_overlap_ratio_below_0.01"
    _write_csv(paths.trace_intersections, trace_rows, list(trace_rows[0]))
    _write_csv(paths.review_queue, review_rows, list(review_rows[0]))

    paths.preview.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_crs(4326).to_file(paths.preview, driver="GeoJSON", index=False)
    gpd.GeoDataFrame(
        [
            {
                "diagnostic_role": "uncovered_operational_boundary_gap",
                "assignment_status": "unassigned",
                "area_m2": gap.area,
                "percent_operational_boundary": 100 * gap.area / boundary.area,
                "trace_intersection_area_m2": trace_gap_area,
                "known_uncertainty": "Coastline/source-boundary mismatch may contribute; no gap was hand-filled",
            }
        ],
        geometry=[gap],
        crs=CANONICAL_CRS,
    ).to_crs(4326).to_file(paths.gap, driver="GeoJSON", index=False)

    raw_after = _raw_state(paths)
    if raw_before != raw_after:
        raise CommunityNormalizationError("Raw source integrity changed")

    named = set(canonical["community_name_source"])
    if not EXPECTED_NAMED_AREAS <= named:
        raise CommunityNormalizationError("Named-area validation failed")
    prohibited_population_terms = (
        "population",
        "evacuation",
        "shelter_demand",
        "compliance",
        "allocation",
    )
    population_or_demand_fields = [
        column
        for column in canonical.columns
        if any(term in column.lower() for term in prohibited_population_terms)
    ]
    if population_or_demand_fields:
        raise CommunityNormalizationError(
            f"Population firewall violated by fields: {population_or_demand_fields}"
        )

    validation = {
        "status": "passed",
        "region_id": "portmore_jamaica_2020",
        "canonical_path": str(paths.canonical),
        "canonical_layer": CANONICAL_LAYER,
        "canonical_crs": CANONICAL_CRS,
        "source": {
            "layer": SOURCE_LAYER,
            "geometry_year": SOURCE_GEOMETRY_YEAR,
            "positive_area_intersection_count": len(intersections),
            "included_count": len(included),
            "trace_count": len(traces),
            "inclusion_threshold_ratio": INCLUSION_THRESHOLD,
            "minimum_included_overlap_percent": float(included["source_overlap_percent"].min()),
            "maximum_excluded_overlap_percent": float(traces["source_overlap_percent"].max()),
            "included_ids": sorted(included_ids),
            "trace_ids": sorted(trace_ids),
        },
        "identity": {
            "record_count": len(stored),
            "unique_non_null_community_ids": int(stored["community_id"].nunique()),
            "unique_non_null_source_ids": int(stored["source_geography_id"].nunique()),
            "uuid_namespace": str(UUID_NAMESPACE),
            "uuid_seed_template": UUID_SEED_TEMPLATE,
        },
        "geometry": {
            "valid_count": int(stored.geometry.is_valid.sum()),
            "non_empty_count": int((~stored.geometry.is_empty).sum()),
            "outside_operational_boundary_area_m2": outside_m2,
            "operational_boundary_area_m2": boundary.area,
            "canonical_union_area_m2": union.area,
            "uncovered_area_m2": gap.area,
            "uncovered_percent": 100 * gap.area / boundary.area,
            "trace_intersections_explain_gap_area_m2": trace_gap_area,
            "trace_intersections_explain_gap_percent": 100 * trace_gap_area / gap.area,
            "overlap": overlap,
        },
        "boundary_review": {
            "crossing_source_unit_count": int(canonical["crosses_operational_boundary"].sum()),
            "edge_review_zone_count": int(canonical["boundary_edge_review_required"].sum()),
            "edge_review_semantics": "two_sided_750m_band_review_only_not_operational_inclusion",
        },
        "named_area_checks": [
            {
                "name": name.title(),
                "present_once": int((canonical["community_name_source"] == name).sum()) == 1,
            }
            for name in sorted(EXPECTED_NAMED_AREAS)
        ],
        "temporal_semantics": {
            "source_geometry_year": 2012,
            "canonical_filename_year": 2020,
            "canonical_filename_year_meaning": "Portmore 2020 regional baseline role; not source geometry vintage",
        },
        "population_firewall": {
            "population_fields_present": population_or_demand_fields,
            "worldpop_acquired": False,
            "population_aggregated": False,
            "evacuation_or_shelter_demand_fields_present": [],
        },
        "licensing": {
            "status": LICENSING_STATUS,
            "permissive_redistribution_claimed": False,
        },
        "raw_integrity": {"unchanged": True, "inputs": raw_after},
    }
    paths.validation.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")

    lineage = {
        "generated_at_utc": recorded,
        "region_id": "portmore_jamaica_2020",
        "source": {
            "originator": "Statistical Institute of Jamaica (STATIN)",
            "repackager": "U.S. Census Bureau (USCB)",
            "product": SOURCE_LAYER,
            "source_geometry_year": 2012,
            "archive": str(paths.source_archive),
            "archive_sha256": SOURCE_CHECKSUM_SHA256,
            "provenance_reference": SOURCE_PROVENANCE_REFERENCE,
            "redistribution_status": LICENSING_STATUS,
            "rights_note": "Public availability and local documentation do not establish permissive redistribution rights",
        },
        "identity": {
            "uuid_namespace": str(UUID_NAMESPACE),
            "namespace_derivation": UUID_NAMESPACE_DERIVATION,
            "seed_template": UUID_SEED_TEMPLATE,
            "independent_of": [
                "display name",
                "normalized name",
                "geometry",
                "area",
                "population",
                "row order",
            ],
        },
        "construction": {
            "method": CONSTRUCTION_METHOD,
            "analysis_crs": CANONICAL_CRS,
            "inclusion_rule": "intersection_area_m2 / source_full_area_m2 >= 0.01",
            "threshold_scope": "Portmore-specific based on observed source geometry separation; not a general threshold",
            "geometry_operation": "source community intersection canonical operational boundary",
            "prohibited_operations": [
                "buffer",
                "snap",
                "gap fill",
                "subdivision",
                "aggregation",
                "silent repair",
            ],
        },
        "temporal_semantics": validation["temporal_semantics"],
        "population_firewall": validation["population_firewall"],
        "outputs": {
            "canonical": {"path": str(paths.canonical), "sha256": sha256(paths.canonical)},
            "source_crosswalk": {
                "path": str(paths.source_crosswalk),
                "sha256": sha256(paths.source_crosswalk),
            },
            "identity_crosswalk": {
                "path": str(paths.identity_crosswalk),
                "sha256": sha256(paths.identity_crosswalk),
            },
            "trace_intersections": {
                "path": str(paths.trace_intersections),
                "sha256": sha256(paths.trace_intersections),
            },
            "preview": {"path": str(paths.preview), "sha256": sha256(paths.preview)},
            "gap": {"path": str(paths.gap), "sha256": sha256(paths.gap)},
            "review_queue": {"path": str(paths.review_queue), "sha256": sha256(paths.review_queue)},
            "validation": {"path": str(paths.validation), "sha256": sha256(paths.validation)},
        },
        "software": {
            "geopandas": gpd.__version__,
            "pyogrio": pyogrio.__version__,
            "shapely": shapely.__version__,
        },
    }
    paths.lineage.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    return validation
