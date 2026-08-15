"""Canonicalize the 2019 ODPEM Portmore shelter records conservatively."""

from __future__ import annotations

import csv
import json
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from pyproj import CRS
from shapely.geometry import Point

from mining_sprint.external_sources import EXTERNAL_SOURCE_COLUMNS, read_csv_records
from mining_sprint.region_normalization import sha256
from mining_sprint.shelter_resolution import load_resolution_inputs

LAYER_NAME = "portmore_shelters_2019"
CANONICAL_CRS = "EPSG:3448"
SOURCE_YEAR = 2019
OSM_ATTRIBUTION = "© OpenStreetMap contributors"
OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
ID_NAMESPACE = uuid.UUID("fd877461-830a-54ad-83a7-c0cbaeb7c004")
SELECTED_LOCATION_IDS = {
    "shelter_candidate_0001": "loc-0001-a",
    "shelter_candidate_0003": "loc-0003-a",
    "shelter_candidate_0005": "loc-0005-a",
    "shelter_candidate_0006": "loc-0006-a",
    "shelter_candidate_0008": "loc-0008-a",
    "shelter_candidate_0010": "loc-0010-a",
    "shelter_candidate_0013": "loc-0013-a",
    "shelter_candidate_0014": "loc-0014-a",
    "shelter_candidate_0015": "loc-0015-a",
    "shelter_candidate_0016": "loc-0016-a",
    "shelter_candidate_0018": "loc-0018-a",
    "shelter_candidate_0019": "loc-0019-a",
    "shelter_candidate_0020": "loc-0020-a",
}


class ShelterCanonicalizationError(RuntimeError):
    """Raised when canonicalization would violate the approved contracts."""


@dataclass(frozen=True)
class ShelterPaths:
    """Inputs and generated outputs for WS25-004 shelter canonicalization."""

    repository_root: Path
    raw_root: Path
    boundary: Path
    edge_review: Path
    context_buffer: Path
    canonical: Path
    preview: Path
    validation: Path
    lineage: Path
    review_queue: Path


def stable_shelter_id(source_record_id: str) -> str:
    """Return an opaque stable ID based only on the immutable source-record ID."""
    return f"shelter_{uuid.uuid5(ID_NAMESPACE, source_record_id).hex}"


def raw_inventory(root: Path) -> dict[str, dict[str, object]]:
    """Hash every existing Raw file without modifying it."""
    return {
        str(path.relative_to(root)): {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def parse_capacity(raw: str) -> tuple[int | None, str]:
    """Parse only unambiguous integer text; blanks and N/A remain missing."""
    if raw == "" or raw.upper() == "N/A":
        return None, "missing"
    if raw.isascii() and raw.isdecimal():
        return int(raw), "stated"
    return None, "ambiguous"


def _read_single_geometry(path: Path, layer: str):
    frame = gpd.read_file(path, layer=layer)
    if len(frame) != 1 or frame.crs != CRS.from_epsg(3448):
        raise ShelterCanonicalizationError(f"Unexpected layer count or CRS: {path}:{layer}")
    geometry = frame.geometry.iloc[0]
    if geometry.is_empty or not geometry.is_valid:
        raise ShelterCanonicalizationError(f"Invalid or empty classification geometry: {path}")
    return geometry


def _selection_decision(location: dict[str, str], alternatives: int) -> str:
    representation = location["coordinate_representation"]
    basis = (
        "Accepted medium-confidence present-day OSM named facility feature consistent with "
        "the ODPEM identity/address and documented official corroboration"
    )
    if alternatives > 1:
        basis += (
            "; selected the broader named facility-area representation and retained alternatives"
        )
    if representation == "computed_way_centroid":
        basis += "; coordinate is a computed OSM way centroid, not a building centroid or entrance"
    return basis


def _review_rows(record: dict[str, object]) -> list[dict[str, str]]:
    rows = []
    categories = {
        "identity": record["identity_review_status"] == "required",
        "priority": record["priority_review_status"] == "required",
        "location": record["location_review_required"],
        "competing_coordinates": record["competing_coordinate_count"] > 1,
        "capacity": record["capacity_status"] != "stated"
        or record["capacity_unit"] == "not_established",
        "areas_served": True,
        "boundary": record["spatial_classification_status"] == "unknown"
        or record["inside_operational_boundary"] is False
        or bool(record["in_boundary_edge_review_band"]),
    }
    for category, required in categories.items():
        if required:
            note = {
                "identity": "Identity decision remains open",
                "priority": "Priority interpretation remains open",
                "location": "Location requires review; null geometry is retained when unresolved",
                "competing_coordinates": "Competing coordinate candidates retained in evidence table",
                "capacity": "Capacity is missing/ambiguous or its unit is not established",
                "areas_served": "Raw text preserved; normalized community matching not yet accepted",
                "boundary": "Spatial result is unknown or falls in the operational edge-review band",
            }[category]
            rows.append(
                {
                    "shelter_id": str(record["shelter_id"]),
                    "source_record_id": str(record["source_record_id"]),
                    "resolution_candidate_id": str(record["resolution_candidate_id"]),
                    "review_category": category,
                    "review_status": "required",
                    "review_note": note,
                }
            )
    return rows


def canonicalize_shelters(paths: ShelterPaths) -> dict[str, object]:
    """Generate the canonical shelter layer, preview, lineage, validation, and queue."""
    raw_before = raw_inventory(paths.raw_root)
    inputs = load_resolution_inputs(paths.repository_root)
    source = inputs["source"]
    provenance = read_csv_records(
        paths.repository_root / "metadata" / "external_source_manifest.csv",
        EXTERNAL_SOURCE_COLUMNS,
    )
    source_provenance = next(r for r in provenance if r["source_id"] == source[0]["source_id"])
    identities = {r["source_record_id"]: r for r in inputs["identity"]}
    priorities = {r["source_record_id"]: r for r in inputs["priority"]}
    locations = inputs["location"]
    by_candidate: dict[str, list[dict[str, str]]] = {}
    for location in locations:
        by_candidate.setdefault(location["canonical_candidate_id"], []).append(location)

    boundary = _read_single_geometry(paths.boundary, "portmore_jamaica_2020")
    edge = _read_single_geometry(paths.edge_review, "portmore_boundary_edge_review_750m")
    context = _read_single_geometry(
        paths.context_buffer, "portmore_acquisition_context_buffer_2000m"
    )
    recorded = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    records: list[dict[str, object]] = []
    geometries = []
    for raw in source:
        source_id = (
            f"odpem2019-pm-{int(raw['section_row_ordinal']):03d}"
            if raw["section"] == "PORTMORE CITY MUNICIPALITY"
            else f"odpem2019-out-{int(raw['section_row_ordinal']):03d}"
        )
        identity = identities[source_id]
        priority = priorities[source_id]
        candidate_id = identity["canonical_candidate_id"]
        selected_id = SELECTED_LOCATION_IDS.get(candidate_id)
        candidates = [r for r in by_candidate[candidate_id] if r["candidate_status"] == "candidate"]
        selected = next((r for r in candidates if r["location_candidate_id"] == selected_id), None)
        if selected_id and selected is None:
            raise ShelterCanonicalizationError(f"Missing selected candidate: {selected_id}")
        geometry = None
        if selected:
            geometry = (
                gpd.GeoSeries(
                    [
                        Point(
                            float(selected["source_longitude"]), float(selected["source_latitude"])
                        )
                    ],
                    crs=4326,
                )
                .to_crs(3448)
                .iloc[0]
            )
            if geometry.is_empty or not geometry.is_valid:
                raise ShelterCanonicalizationError(f"Invalid selected point: {selected_id}")
        capacity, capacity_status = parse_capacity(raw["capacity_raw"])
        spatial_status = "classified" if geometry else "unknown"
        source_outside = raw["section"] == "Emergency Shelter outside Portmore"
        record: dict[str, object] = {
            "shelter_id": stable_shelter_id(source_id),
            "source_record_id": source_id,
            "resolution_candidate_id": candidate_id,
            "source_id": raw["source_id"],
            "source_checksum_sha256": source_provenance["sha256"],
            "source_provenance_reference": "metadata/external_source_manifest.csv#source_id=odpem_portmore_shelters_2019",
            "display_name": identity["normalized_display_name_candidate"],
            "source_name_raw": raw["shelter_name_raw"],
            "source_section_raw": raw["section"],
            "source_page": int(raw["source_page"]),
            "source_section_row_ordinal": int(raw["section_row_ordinal"]),
            "source_document_row_ordinal": int(raw["document_row_ordinal"]),
            "parish_raw": raw["parish_raw"],
            "local_authority_raw": raw["local_authority_raw"],
            "shelter_address_raw": raw["shelter_address_raw"],
            "community_raw": raw["community_raw"],
            "priority_shelter_raw": raw["priority_shelter_raw"],
            "capacity_raw": raw["capacity_raw"],
            "zone_raw": raw["zone_raw"],
            "areas_served_raw": raw["areas_served_raw"],
            "source_capacity": capacity,
            "source_capacity_unit": "not_established",
            "baseline_capacity": capacity,
            "baseline_capacity_semantics": "historical_source_value_with_unestablished_unit_not_verified_operational_capacity",
            "historical_listed_capacity": capacity,
            "capacity_status": capacity_status,
            "capacity_unit": "not_established",
            "capacity_conflict_note": None,
            "operational_usable_capacity": None,
            "operational_capacity_status": "unknown",
            "source_year": SOURCE_YEAR,
            "designation_baseline": "odpem_listed_designated",
            "event_specific_status": "unknown",
            "operational_availability": "unknown",
            "system_recorded_at_utc": recorded,
            "human_override_status": None,
            "human_override_value": None,
            "human_override_recorded_at_utc": None,
            "priority_interpretation": priority["normalized_priority_interpretation"],
            "priority_review_status": priority["manual_review_status"],
            "identity_confidence": identity["identity_confidence"],
            "identity_review_status": identity["manual_review_status"],
            "areas_served_normalized": None,
            "areas_served_match_method": "not_performed",
            "areas_served_match_confidence": "unresolved",
            "areas_served_review_status": "required",
            "selected_location_candidate_id": selected_id,
            "location_confidence": selected["confidence"] if selected else "unresolved",
            "location_precision_class": selected["precision_class"] if selected else "unresolved",
            "location_selection_decision": (
                _selection_decision(selected, len(candidates))
                if selected
                else "No defensible selection; geometry remains null"
            ),
            "location_review_required": True,
            "competing_coordinate_count": len(candidates),
            "location_source_url": selected["source_url"] if selected else None,
            "location_source_publisher": selected["publisher"] if selected else None,
            "location_source_crs": selected["source_crs"] if selected else None,
            "location_source_latitude": float(selected["source_latitude"]) if selected else None,
            "location_source_longitude": float(selected["source_longitude"]) if selected else None,
            "osm_type": selected["osm_type"] if selected else None,
            "osm_id": selected["osm_id"] if selected else None,
            "osm_coordinate_representation": selected["coordinate_representation"]
            if selected
            else None,
            "osm_licence": selected["licence_identifier"] if selected else None,
            "osm_attribution": OSM_ATTRIBUTION if selected else None,
            "osm_attribution_url": OSM_COPYRIGHT_URL if selected else None,
            "spatial_classification_status": spatial_status,
            "inside_operational_boundary": boundary.covers(geometry) if geometry else None,
            "in_boundary_edge_review_band": edge.covers(geometry) if geometry else None,
            "in_acquisition_context_buffer": context.covers(geometry) if geometry else None,
            "source_defined_outside_portmore_emergency_shelter": source_outside,
            "source_defined_relevance": (
                "odpem_explicit_outside_portmore_emergency_shelter"
                if source_outside
                else "odpem_portmore_municipality_listing"
            ),
            "identity_uncertainty": (
                identity["decision_note"]
                if identity["manual_review_status"] == "required"
                else "none_recorded"
            ),
            "priority_uncertainty": priority["decision_note"],
            "location_uncertainty": (
                selected["source_conflicts"] if selected else "No defensible coordinate selection"
            ),
            "capacity_uncertainty": (
                "source value missing and capacity unit not established"
                if capacity is None
                else "capacity unit not established; operational usability unknown"
            ),
            "boundary_uncertainty": (
                "MVP operational boundary classification is not a legal municipal determination"
                if geometry
                else "classification unknown because canonical geometry is null"
            ),
            "boundary_classification_caveat": (
                "MVP operational classification; not a legal municipal determination"
                if geometry
                else "Unknown because canonical geometry is null"
            ),
        }
        records.append(record)
        geometries.append(geometry)

    frame = gpd.GeoDataFrame(pd.DataFrame(records), geometry=geometries, crs=CANONICAL_CRS)
    paths.canonical.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(paths.canonical, layer=LAYER_NAME, driver="GPKG", index=False)
    stored = gpd.read_file(paths.canonical, layer=LAYER_NAME)
    paths.preview.parent.mkdir(parents=True, exist_ok=True)
    stored.to_crs(4326).to_file(paths.preview, driver="GeoJSON", index=False)

    review_rows = [row for record in records for row in _review_rows(record)]
    with paths.review_queue.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(review_rows[0]))
        writer.writeheader()
        writer.writerows(review_rows)

    raw_after = raw_inventory(paths.raw_root)
    if raw_before != raw_after:
        raise ShelterCanonicalizationError("Raw integrity changed during canonicalization")
    if len(stored) != 20 or stored["shelter_id"].nunique() != 20:
        raise ShelterCanonicalizationError("Canonical record count or shelter IDs failed")
    null_count = int(stored.geometry.isna().sum())
    if null_count != 7:
        raise ShelterCanonicalizationError(f"Expected seven null geometries; found {null_count}")
    non_null = stored.loc[stored.geometry.notna()]
    if not non_null.geometry.is_valid.all() or non_null.geometry.is_empty.any():
        raise ShelterCanonicalizationError("Accepted geometry validity failed")
    if any(
        raw["capacity_raw"] in {"", "N/A"} and record["historical_listed_capacity"] == 0
        for raw, record in zip(source, records, strict=True)
    ):
        raise ShelterCanonicalizationError("Missing capacity became zero")
    raw_columns = {
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
    if any(
        raw[src] != record[dst]
        for raw, record in zip(source, records, strict=True)
        for src, dst in raw_columns.items()
    ) or any(
        int(raw[src]) != record[dst]
        for raw, record in zip(source, records, strict=True)
        for src, dst in {
            "source_page": "source_page",
            "section_row_ordinal": "source_section_row_ordinal",
            "document_row_ordinal": "source_document_row_ordinal",
        }.items()
    ):
        raise ShelterCanonicalizationError("A source/raw value changed")

    validation = {
        "status": "passed",
        "canonical_record_count": len(stored),
        "unique_shelter_id_count": int(stored["shelter_id"].nunique()),
        "source_record_traceability_count": int(stored["source_record_id"].nunique()),
        "crs": str(stored.crs),
        "geometry": {
            "accepted_count": len(non_null),
            "null_count": null_count,
            "accepted_valid_count": int(non_null.geometry.is_valid.sum()),
            "accepted_non_empty_count": int((~non_null.geometry.is_empty).sum()),
            "precision_counts": dict(Counter(non_null["location_precision_class"])),
        },
        "capacity": {
            "status_counts": dict(Counter(stored["capacity_status"])),
            "numeric_count": int(stored["historical_listed_capacity"].notna().sum()),
            "missing_never_zero": True,
            "unit": "not_established",
            "operational_capacity_populated_count": int(
                stored["operational_usable_capacity"].notna().sum()
            ),
        },
        "spatial_classification": {
            "inside_operational_boundary": sum(
                record["inside_operational_boundary"] is True for record in records
            ),
            "outside_operational_boundary": sum(
                record["inside_operational_boundary"] is False for record in records
            ),
            "in_edge_review_band": sum(
                record["in_boundary_edge_review_band"] is True for record in records
            ),
            "in_context_buffer": sum(
                record["in_acquisition_context_buffer"] is True for record in records
            ),
            "outside_context_buffer": sum(
                record["in_acquisition_context_buffer"] is False for record in records
            ),
            "null_geometry_classifications_unknown": bool(
                stored.loc[stored.geometry.isna(), "spatial_classification_status"]
                .eq("unknown")
                .all()
            ),
            "classification_semantics": "MVP operational, not legal municipal determination",
        },
        "outside_portmore_source_records_retained": int(
            stored["source_defined_outside_portmore_emergency_shelter"].sum()
        ),
        "raw_values_unchanged": True,
        "raw_integrity": {"unchanged": True, "files": raw_after},
        "osm_attribution": {"text": OSM_ATTRIBUTION, "url": OSM_COPYRIGHT_URL},
        "review_queue_rows": len(review_rows),
    }
    paths.validation.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")

    lineage = {
        "generated_at_utc": recorded,
        "canonical_path": str(paths.canonical),
        "canonical_layer": LAYER_NAME,
        "canonical_crs": CANONICAL_CRS,
        "shelter_id_contract": {
            "method": "UUIDv5 over immutable ODPEM source_record_id with project namespace",
            "independent_of": ["display_name", "geometry"],
            "crosswalk_fields": ["source_record_id", "resolution_candidate_id"],
            "silent_merges": False,
        },
        "source": source_provenance,
        "location_evidence": {
            "selected_candidate_ids": SELECTED_LOCATION_IDS,
            "osm_attribution": OSM_ATTRIBUTION,
            "osm_copyright_url": OSM_COPYRIGHT_URL,
            "licence": "ODbL-1.0",
            "temporal_limitation": "Present-day location evidence does not establish 2019/2020 operation or availability",
        },
        "boundary_inputs": {
            "canonical": {"path": str(paths.boundary), "sha256": sha256(paths.boundary)},
            "edge_review": {"path": str(paths.edge_review), "sha256": sha256(paths.edge_review)},
            "context_buffer": {
                "path": str(paths.context_buffer),
                "sha256": sha256(paths.context_buffer),
            },
        },
        "outputs": {
            "canonical": {"path": str(paths.canonical), "sha256": sha256(paths.canonical)},
            "preview": {"path": str(paths.preview), "sha256": sha256(paths.preview)},
            "validation": {"path": str(paths.validation), "sha256": sha256(paths.validation)},
            "review_queue": {"path": str(paths.review_queue), "sha256": sha256(paths.review_queue)},
        },
        "software": {
            "geopandas": gpd.__version__,
            "pyogrio": pyogrio.__version__,
            "shapely": shapely.__version__,
        },
    }
    paths.lineage.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    return validation
