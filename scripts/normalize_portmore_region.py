"""Create the canonical Portmore region package from immutable Raw inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from mining_sprint.paths import interim_dir, outputs_dir, processed_dir, raw_dir
from mining_sprint.region_normalization import (
    RegionNormalizationError,
    RegionPaths,
    normalize_region,
)


def default_paths() -> RegionPaths:
    """Return repository-conventional project-data paths."""
    output_root = outputs_dir() / "ws25-003"
    return RegionPaths(
        item_metadata=raw_dir() / "410bc3258e7046f6a944e070159f2d38-item.json",
        item_data=raw_dir() / "410bc3258e7046f6a944e070159f2d38-data.json",
        census_archive=raw_dir() / "jamaica.gdb.zip",
        canonical=processed_dir() / "region" / "portmore_boundary.gpkg",
        edge_review=interim_dir() / "region" / "portmore_boundary_edge_review_750m.gpkg",
        context_buffer=(
            interim_dir() / "region" / "portmore_acquisition_context_buffer_2000m.gpkg"
        ),
        preview=output_root / "portmore_boundary_preview_epsg4326.geojson",
        validation=output_root / "validation.json",
        lineage=output_root / "lineage.json",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-data-root",
        type=Path,
        help="Override all Raw/Interim/Processed/Outputs paths for testing or isolated runs",
    )
    args = parser.parse_args()
    paths = default_paths()
    if args.project_data_root:
        root = args.project_data_root
        output_root = root / "Outputs" / "ws25-003"
        paths = RegionPaths(
            item_metadata=root / "Raw" / paths.item_metadata.name,
            item_data=root / "Raw" / paths.item_data.name,
            census_archive=root / "Raw" / paths.census_archive.name,
            canonical=root / "Processed" / "region" / paths.canonical.name,
            edge_review=root / "Interim" / "region" / paths.edge_review.name,
            context_buffer=root / "Interim" / "region" / paths.context_buffer.name,
            preview=output_root / paths.preview.name,
            validation=output_root / paths.validation.name,
            lineage=output_root / paths.lineage.name,
        )
    try:
        validation = normalize_region(paths)
    except RegionNormalizationError as error:
        raise SystemExit(f"Portmore region normalization failed: {error}") from error
    print(f"Wrote canonical boundary: {validation['canonical_path']}")
    print(f"Wrote validation: {paths.validation}")


if __name__ == "__main__":
    main()
