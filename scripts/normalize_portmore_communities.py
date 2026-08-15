"""Generate canonical WS25-005 Portmore community-zone artifacts."""

from __future__ import annotations

from mining_sprint.community_normalization import (
    CommunityNormalizationError,
    CommunityPaths,
    normalize_communities,
)
from mining_sprint.paths import interim_dir, outputs_dir, processed_dir, raw_dir


def default_paths() -> CommunityPaths:
    """Return repository-conventional mounted project-data paths."""
    output_root = outputs_dir() / "ws25-005"
    interim_root = interim_dir() / "communities"
    return CommunityPaths(
        source_archive=raw_dir() / "jamaica.gdb.zip",
        source_workbook=raw_dir() / "jamaica_uscb_202302.xlsx",
        source_metadata_pdf=raw_dir() / "geo-metadata-pgs-uscb-dec16.pdf",
        source_linkage_pdf=raw_dir() / "readme-poplinkagetoshapefile-instructions.pdf",
        boundary=processed_dir() / "region" / "portmore_boundary.gpkg",
        edge_review=interim_dir() / "region" / "portmore_boundary_edge_review_750m.gpkg",
        canonical=processed_dir() / "communities" / "portmore_community_zones_2020.gpkg",
        source_crosswalk=interim_root / "portmore_source_unit_crosswalk.csv",
        identity_crosswalk=interim_root / "portmore_community_identity_crosswalk.csv",
        trace_intersections=interim_root / "portmore_trace_intersections.csv",
        validation=output_root / "validation.json",
        lineage=output_root / "lineage.json",
        preview=output_root / "portmore_community_zones_preview_epsg4326.geojson",
        gap=output_root / "operational_boundary_gap.geojson",
        review_queue=output_root / "review_queue.csv",
    )


def main() -> None:
    try:
        validation = normalize_communities(default_paths())
    except CommunityNormalizationError as error:
        raise SystemExit(f"Community normalization failed: {error}") from error
    print(f"Canonical zones: {validation['identity']['record_count']}")
    print(f"Trace intersections: {validation['source']['trace_count']}")
    print(f"Uncovered area m2: {validation['geometry']['uncovered_area_m2']}")


if __name__ == "__main__":
    main()
