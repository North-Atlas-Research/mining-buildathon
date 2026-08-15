"""Attach the approved local-demographic baseline to frozen Portmore zones."""

from __future__ import annotations

from mining_sprint.paths import interim_dir, outputs_dir, processed_dir, raw_dir
from mining_sprint.population_normalization import (
    PopulationNormalizationError,
    PopulationPaths,
    normalize_population,
)


def default_paths() -> PopulationPaths:
    return PopulationPaths(
        canonical=processed_dir() / "communities/portmore_community_zones_2020.gpkg",
        boundary=processed_dir() / "region/portmore_boundary.gpkg",
        source_archive=raw_dir() / "jamaica.gdb.zip",
        anchor_data=raw_dir() / "410bc3258e7046f6a944e070159f2d38-data.json",
        source_workbook=raw_dir() / "jamaica_uscb_202302.xlsx",
        audit_csv=interim_dir() / "population/portmore_local_2020_population_baseline.csv",
        validation=outputs_dir() / "ws25-005/validation.json",
        lineage=outputs_dir() / "ws25-005/lineage.json",
        preview=outputs_dir() / "ws25-005/community_population_preview_epsg4326.geojson",
        review_queue=outputs_dir() / "ws25-005/review_queue.csv",
    )


def main() -> None:
    try:
        validation = normalize_population(default_paths())
    except PopulationNormalizationError as error:
        raise SystemExit(f"Population normalization failed: {error}") from error
    print(
        f"Projected Portmore 2020 baseline: {validation['projection']['projected_portmore_2020']}"
    )


if __name__ == "__main__":
    main()
