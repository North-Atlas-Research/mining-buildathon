"""Attach the approved local-demographic 2020 baseline to frozen community zones."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
from pyproj import CRS

from mining_sprint.community_normalization import CANONICAL_CRS, CANONICAL_LAYER
from mining_sprint.region_normalization import sha256

PORTMORE_ANCHOR = 182153
SAINT_CATHERINE_2011 = 516218
SAINT_CATHERINE_2019 = 520502
TARGET_YEAR = 2020
ANCHOR_YEAR = 2011
DISTRIBUTION_YEAR = 2012
POV_ESTP_TOTAL = 171546.0
POVERTY_LAYER = "JM_POVERTY_GEOG2_2012survey_uscb_202302"
PROJECTION_METHOD = "saint_catherine_2011_2019_cagr_extended_to_2020"
DISTRIBUTION_METHOD = "normalized_2012_community_population_estimate_weights"
WORLDPOP_REJECTED_SOURCES = {
    "constrained": {
        "product": "jam_ppp_2020_UNadj_constrained.tif",
        "doi": "10.5258/SOTON/WP00685",
        "operational_boundary_total": 108219.5982,
    },
    "unconstrained": {
        "product": "jam_ppp_2020_UNadj.tif",
        "doi": "10.5258/SOTON/WP00660",
        "operational_boundary_total": 114233.6475,
    },
}


class PopulationNormalizationError(RuntimeError):
    """Raised when the approved local-population contract cannot be met."""


@dataclass(frozen=True)
class PopulationPaths:
    canonical: Path
    boundary: Path
    source_archive: Path
    anchor_data: Path
    source_workbook: Path
    audit_csv: Path
    validation: Path
    lineage: Path
    preview: Path
    review_queue: Path


def projected_portmore_population_2020() -> float:
    """Return the approved reproducible nine-year parish-proxy projection."""
    return PORTMORE_ANCHOR * ((SAINT_CATHERINE_2019 / SAINT_CATHERINE_2011) ** (9 / 8))


def _raw_state(paths: PopulationPaths) -> dict[str, dict[str, object]]:
    return {
        path.name: {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in (paths.source_archive, paths.anchor_data, paths.source_workbook)
    }


def _require_anchor(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    layer = next(item for item in data["operationalLayers"] if item["title"] == "Portmore - 02")
    attrs = layer["featureCollection"]["layers"][0]["featureSet"]["features"][0]["attributes"]
    if (
        attrs["TOTAL_POP"] != PORTMORE_ANCHOR
        or attrs["MALE_POP"] + attrs["FEMALE_POP"] != PORTMORE_ANCHOR
    ):
        raise PopulationNormalizationError("Frozen STATIN Portmore anchor does not reconcile")


def _pov_estp(paths: PopulationPaths) -> dict[str, float]:
    evidence = gpd.read_file(f"/vsizip/{paths.source_archive}/Jamaica.gdb", layer=POVERTY_LAYER)
    if evidence["GEO_MATCH"].isna().any() or evidence["GEO_MATCH"].duplicated().any():
        raise PopulationNormalizationError("POV_ESTP source identifiers are null or duplicate")
    return {
        key: float(value)
        for key, value in zip(evidence["GEO_MATCH"], evidence["POV_ESTP"], strict=True)
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _review_queue(path: Path, rows: list[dict[str, str]]) -> None:
    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as source:
            existing = list(csv.DictReader(source))
    existing = [
        row
        for row in existing
        if row.get("review_category")
        not in {"population_baseline_uncertainty", "population_partial_pixel_dependence"}
    ]
    all_rows = existing + rows
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(
            target, fieldnames=list(dict.fromkeys(key for row in all_rows for key in row))
        )
        writer.writeheader()
        writer.writerows(all_rows)


def _geometry_guard(before: gpd.GeoDataFrame, after: gpd.GeoDataFrame) -> None:
    if list(before["community_id"]) != list(after["community_id"]) or list(
        before["source_geography_id"]
    ) != list(after["source_geography_id"]):
        raise PopulationNormalizationError("Population attachment changed frozen identities")
    if not all(
        left.equals_exact(right, tolerance=0.0)
        for left, right in zip(before.geometry, after.geometry, strict=True)
    ):
        raise PopulationNormalizationError("Population attachment changed frozen zone geometry")


def normalize_population(paths: PopulationPaths) -> dict[str, object]:
    """Attach the approved projected local-demographic baseline without changing zones."""
    raw_before = _raw_state(paths)
    _require_anchor(paths.anchor_data)
    zones = gpd.read_file(paths.canonical, layer=CANONICAL_LAYER)
    boundary = gpd.read_file(paths.boundary, layer="portmore_jamaica_2020")
    if (
        len(zones) != 14
        or zones.crs != CRS.from_epsg(3448)
        or len(boundary) != 1
        or boundary.crs != CRS.from_epsg(3448)
    ):
        raise PopulationNormalizationError("Frozen zone or boundary count/CRS changed")
    if (
        zones["community_id"].isna().any()
        or not zones["community_id"].is_unique
        or zones["source_geography_id"].isna().any()
        or not zones["source_geography_id"].is_unique
    ):
        raise PopulationNormalizationError("Frozen identifiers are null or duplicate")
    if zones.geometry.is_empty.any() or not zones.geometry.is_valid.all():
        raise PopulationNormalizationError("Frozen zone geometry is invalid or empty")
    frozen = zones.copy()
    evidence = _pov_estp(paths)
    missing = set(zones["source_geography_id"]) - set(evidence)
    if missing:
        raise PopulationNormalizationError(f"POV_ESTP evidence missing for {sorted(missing)}")
    values = [evidence[identifier] for identifier in zones["source_geography_id"]]
    if any(value < 0 for value in values) or sum(values) != POV_ESTP_TOTAL:
        raise PopulationNormalizationError("Frozen 2012 POV_ESTP total does not reproduce")
    total = projected_portmore_population_2020()
    weights = [value / POV_ESTP_TOTAL for value in values]
    estimates = [total * weight for weight in weights]
    if abs(sum(weights) - 1) > 1e-12 or abs(sum(estimates) - total) > 1e-8:
        raise PopulationNormalizationError("Population totals do not reconcile")
    zones = zones.drop(
        columns=[
            column
            for column in zones
            if column.startswith("population_")
            or column in {"resident_population_estimate", "resident_population_display_rounded"}
        ],
        errors="ignore",
    )
    caveat = (
        "Projected 2020 baseline, not observed census, event-day population, evacuation population, or shelter demand. "
        "Portmore TOTAL_POP is a 2011 field labelled TOTAL POPULATION and is not explicitly labelled resident population; "
        "Saint Catherine parish growth is a proxy; 2012 community population estimates provide proportional weights; "
        "the small operational-boundary gap is not represented as a separate demographic unit."
    )
    zones["pov_estp_2012"] = values
    zones["population_distribution_weight"] = weights
    zones["resident_population_estimate"] = estimates
    zones["population_unit"] = "people"
    zones["population_estimate_basis"] = "projected_local_demographic_baseline"
    zones["population_anchor_source"] = (
        "STATIN ArcGIS Jamaica: Special Areas and Population 2011 / Portmore - 02 / TOTAL_POP"
    )
    zones["population_anchor_year"] = ANCHOR_YEAR
    zones["population_projection_method"] = PROJECTION_METHOD
    zones["population_projection_source"] = (
        "STATIN Saint Catherine 2011 census and 2019 mid-year estimate"
    )
    zones["population_distribution_method"] = DISTRIBUTION_METHOD
    zones["population_distribution_source"] = f"STATIN/USCB {POVERTY_LAYER}.POV_ESTP"
    zones["population_distribution_year"] = DISTRIBUTION_YEAR
    zones["population_temporal_uncertainty"] = "moderate"
    zones["population_spatial_uncertainty"] = "moderate"
    zones["population_review_required"] = True
    zones["known_uncertainty"] = zones["known_uncertainty"].astype(str) + " " + caveat
    gap = boundary.geometry.iloc[0].difference(frozen.geometry.union_all())
    if gap.is_empty or gap.area <= 0:
        raise PopulationNormalizationError("Frozen operational-boundary gap unexpectedly absent")
    temporary = paths.canonical.with_suffix(".population-tmp.gpkg")
    zones.to_file(temporary, layer=CANONICAL_LAYER, driver="GPKG", index=False)
    stored = gpd.read_file(temporary, layer=CANONICAL_LAYER)
    if (
        len(stored) != 14
        or stored.crs != CRS.from_epsg(3448)
        or stored.geometry.is_empty.any()
        or not stored.geometry.is_valid.all()
    ):
        raise PopulationNormalizationError("Temporary canonical artifact failed validation")
    _geometry_guard(frozen, stored)
    temporary.replace(paths.canonical)
    audit_rows = [
        {
            "community_id": r.community_id,
            "community_name": r.community_name,
            "source_geography_id": r.source_geography_id,
            "POV_ESTP_2012": value,
            "distribution_weight": weight,
            "projected_population_2020": estimate,
            "population_anchor_year": ANCHOR_YEAR,
            "population_projection_method": PROJECTION_METHOD,
            "population_distribution_method": DISTRIBUTION_METHOD,
            "review_required": True,
        }
        for r, value, weight, estimate in zip(
            zones.itertuples(), values, weights, estimates, strict=True
        )
    ]
    _write_csv(paths.audit_csv, audit_rows)
    _review_queue(
        paths.review_queue,
        [
            {
                "community_id": r.community_id,
                "source_geography_id": r.source_geography_id,
                "source_geography_name": r.source_geography_name,
                "review_category": "population_baseline_uncertainty",
                "review_status": "required",
                "review_note": "Projected local-demographic 2020 baseline uses parish proxy and 2012 community weights; it is not an observed 2020 count.",
            }
            for r in zones.itertuples()
        ],
    )
    stored.to_crs(4326).to_file(paths.preview, driver="GeoJSON", index=False)
    raw_after = _raw_state(paths)
    if raw_before != raw_after:
        raise PopulationNormalizationError("Raw input changed during processing")
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    validation = {
        "status": "passed",
        "population_baseline": "projected 2020 Portmore population baseline; not observed census, event-day population, evacuation population, or shelter demand",
        "canonical": {
            "path": str(paths.canonical),
            "layer": CANONICAL_LAYER,
            "record_count": 14,
            "crs": CANONICAL_CRS,
        },
        "identity_and_geometry": {
            "community_ids_unchanged": True,
            "source_geography_ids_unchanged": True,
            "geometry_exactly_unchanged": True,
            "valid_non_empty_geometry_count": int(stored.geometry.is_valid.sum()),
            "gap_area_m2": gap.area,
            "gap_area_percent_of_boundary": 100 * gap.area / boundary.geometry.iloc[0].area,
        },
        "projection": {
            "anchor_value": PORTMORE_ANCHOR,
            "anchor_year": ANCHOR_YEAR,
            "saint_catherine_2011": SAINT_CATHERINE_2011,
            "saint_catherine_2019": SAINT_CATHERINE_2019,
            "target_year": TARGET_YEAR,
            "formula": "182153 * ((520502 / 516218) ** (9 / 8))",
            "projected_portmore_2020": total,
            "annual_factor": (SAINT_CATHERINE_2019 / SAINT_CATHERINE_2011) ** (1 / 8),
        },
        "distribution": {
            "source_layer": POVERTY_LAYER,
            "field": "POV_ESTP",
            "source_year": DISTRIBUTION_YEAR,
            "source_total": POV_ESTP_TOTAL,
            "weight_sum": sum(weights),
            "population_sum": sum(estimates),
            "minimum_population": min(estimates),
            "maximum_population": max(estimates),
        },
        "worldpop": {
            "canonical_source_status": "rejected_primary_population_source",
            "reason": "Technically validated WorldPop products materially under-allocated Portmore population relative to stronger local 2011/2012 demographic evidence and are retained as contextual/rejected evidence.",
            "sources": WORLDPOP_REJECTED_SOURCES,
        },
        "population_firewall": {
            "population_to_demand_conversion": False,
            "demand_fields_present": [],
        },
        "raw_integrity": {"unchanged": raw_before == raw_after, "inputs": raw_after},
        "generated_at_utc": generated_at,
    }
    paths.validation.parent.mkdir(parents=True, exist_ok=True)
    paths.validation.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    lineage = {
        "generated_at_utc": generated_at,
        "canonical_population_decision": "approved_projected_local_demographic_baseline",
        "lineage": [
            "STATIN ArcGIS 2011 Portmore TOTAL_POP (spatially matched anchor)",
            "STATIN Saint Catherine 2011 census to 2019 mid-year trend (parish proxy extended to 2020)",
            "STATIN/USCB 2012 POV_ESTP community estimates (normalized distribution weights)",
            "frozen 14 canonical planning zones",
            "projected 2020 Portmore population baseline",
        ],
        "worldpop_decision_path": {
            "constrained": "technically_validated_then_rejected_as_primary",
            "unconstrained": "technically_validated_then_rejected_as_primary",
            "reason": validation["worldpop"]["reason"],
        },
        "outputs": {
            "canonical": str(paths.canonical),
            "audit_csv": str(paths.audit_csv),
            "preview": str(paths.preview),
            "validation": str(paths.validation),
            "review_queue": str(paths.review_queue),
        },
        "raw_inputs": raw_after,
    }
    paths.lineage.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    return validation
