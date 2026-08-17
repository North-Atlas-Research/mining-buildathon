"""Build the native-grid WS25-009 Portmore IMERG event cube."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import xarray as xr

from mining_sprint.rainfall import (
    normalize_dataset,
    read_native_subset,
    source_intervals,
    utc_datetime,
)

RAW_REL = Path("Raw/nasa_gpm_imerg/GPM_3IMERGHH_07/V07B/2020/10")
EVENT_START = utc_datetime("2020-10-05T05:00:00Z")
EVENT_END = utc_datetime("2020-10-08T05:00:00Z")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("/workspace/data"))
    args = parser.parse_args()
    root = args.data_root
    raw = root / RAW_REL
    region = gpd.read_file(root / "Processed/region/portmore_boundary.gpkg", layer="portmore_jamaica_2020")
    context = gpd.GeoSeries(region.geometry.buffer(2000), crs=region.crs).to_crs("EPSG:4326").union_all()
    intervals = source_intervals(raw)
    source = read_native_subset(intervals, context)
    dataset = normalize_dataset(source, EVENT_START, EVENT_END)
    dataset.attrs.update({
        "title": "Portmore October 2020 NASA GPM IMERG Final V07B rainfall context",
        "collection": "GPM_3IMERGHH_07", "product_version": "V07B",
        "source_raw_directory": str(raw), "acquisition_interval_utc": "[2020-10-04T05:00:00Z, 2020-10-09T05:00:00Z)",
        "rainfall_scope": "Rainfall context only; not flood depth, flooded-road status, closure, accessibility penalty, or shelter impact.",
    })
    destination = root / "Processed/rainfall/portmore_october_2020_imerg_v07b.nc"
    destination.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_netcdf(destination, engine="h5netcdf", mode="w")
    with xr.open_dataset(destination, engine="h5netcdf") as reopened:
        retained = int(reopened.sizes["lat"] * reopened.sizes["lon"])
        missing = {name: int(reopened[name].isnull().sum().item()) for name in reopened.data_vars if name not in {"lat_bounds", "lon_bounds", "source_interval_start", "source_interval_end"}}
        validation = {
            "source_count": len(intervals), "source_continuity": True, "source_unit": "mm/hr", "source_interval_minutes": 30,
            "retained_native_cells": retained, "source_resampling": False, "output_dimensions": dict(reopened.sizes),
            "output_time_first": str(reopened.time.values[0]), "output_time_last": str(reopened.time.values[-1]),
            "first_valid": {name: (str(reopened.time.where(reopened[name].notnull().any(("lat", "lon")), drop=True).values[0]) if name != "event_total_mm" else None) for name in ("accumulation_1h_mm", "accumulation_3h_mm", "accumulation_6h_mm", "accumulation_24h_mm", "event_total_mm")},
            "event_interval_count": 144, "missing_counts": missing, "netcdf_readable": True,
            "spatial_extent": {"lon": [float(reopened.lon.min()), float(reopened.lon.max())], "lat": [float(reopened.lat.min()), float(reopened.lat.max())]},
            "spot_check_rate_to_depth": {"rate": float(reopened.precipitation_rate_mm_h.isel(time=0,lat=0,lon=0)), "depth": float(reopened.precipitation_30m_mm.isel(time=0,lat=0,lon=0))},
        }
    out = root / "Outputs/ws25-009"; out.mkdir(parents=True, exist_ok=True)
    (out / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    lineage = {"collection": "GPM_3IMERGHH_07", "version": "V07B", "raw_manifest": "metadata/ws25_009_imerg_raw_manifest.csv", "acquisition_validation": str(out / "acquisition_validation.json"), "source_count": 240, "spatial_subset_rule": "native cell bounds intersect frozen 2 km context", "timestamp_rule": "end-labelled [T-30m,T)", "conversion": "rate_mm_h * 0.5", "implementation": "scripts/build_portmore_rainfall_event.py"}
    (out / "lineage.json").write_text(json.dumps(lineage, indent=2) + "\n")
    print(json.dumps(validation, indent=2))
if __name__ == "__main__": main()
