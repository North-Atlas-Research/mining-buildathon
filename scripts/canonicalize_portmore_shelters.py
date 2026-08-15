"""Generate canonical WS25-004 shelter artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from mining_sprint.paths import interim_dir, outputs_dir, processed_dir, raw_dir
from mining_sprint.shelter_canonicalization import (
    ShelterCanonicalizationError,
    ShelterPaths,
    canonicalize_shelters,
)

ROOT = Path(__file__).resolve().parents[1]


def default_paths() -> ShelterPaths:
    """Return repository-conventional project-data paths."""
    output_root = outputs_dir() / "ws25-004"
    return ShelterPaths(
        repository_root=ROOT,
        raw_root=raw_dir(),
        boundary=processed_dir() / "region" / "portmore_boundary.gpkg",
        edge_review=interim_dir() / "region" / "portmore_boundary_edge_review_750m.gpkg",
        context_buffer=interim_dir() / "region" / "portmore_acquisition_context_buffer_2000m.gpkg",
        canonical=processed_dir() / "shelters" / "portmore_shelters_2019.gpkg",
        preview=output_root / "portmore_shelters_2019_preview_epsg4326.geojson",
        validation=output_root / "validation.json",
        lineage=output_root / "lineage.json",
        review_queue=output_root / "consolidated_review_queue.csv",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-data-root",
        type=Path,
        help="Override generated data and boundary paths; repository metadata remains authoritative",
    )
    args = parser.parse_args()
    paths = default_paths()
    if args.project_data_root:
        root = args.project_data_root
        paths = ShelterPaths(
            repository_root=ROOT,
            raw_root=root / "Raw",
            boundary=root / "Processed" / "region" / "portmore_boundary.gpkg",
            edge_review=root / "Interim" / "region" / "portmore_boundary_edge_review_750m.gpkg",
            context_buffer=root
            / "Interim"
            / "region"
            / "portmore_acquisition_context_buffer_2000m.gpkg",
            canonical=root / "Processed" / "shelters" / "portmore_shelters_2019.gpkg",
            preview=root
            / "Outputs"
            / "ws25-004"
            / "portmore_shelters_2019_preview_epsg4326.geojson",
            validation=root / "Outputs" / "ws25-004" / "validation.json",
            lineage=root / "Outputs" / "ws25-004" / "lineage.json",
            review_queue=root / "Outputs" / "ws25-004" / "consolidated_review_queue.csv",
        )
    try:
        result = canonicalize_shelters(paths)
    except ShelterCanonicalizationError as error:
        raise SystemExit(f"Shelter canonicalization failed: {error}") from error
    print(f"Wrote {result['canonical_record_count']} canonical shelter records")
    print(f"Accepted geometries: {result['geometry']['accepted_count']}")
    print(f"Explicit null geometries: {result['geometry']['null_count']}")


if __name__ == "__main__":
    main()
