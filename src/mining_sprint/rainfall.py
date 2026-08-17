"""Native-grid IMERG rainfall normalization primitives for WS25-009."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import h5py
import numpy as np
import xarray as xr
from shapely.geometry import box

SOURCE_INTERVAL = timedelta(minutes=30)
FILENAME = re.compile(
    r"^3B-HHR\.MS\.MRG\.3IMERG\.(?P<date>\d{8})-S(?P<start>\d{6})-E(?P<end>\d{6})\.\d{4}\.V07B\.HDF5$"
)


class RainfallSourceError(RuntimeError):
    """Raised when an immutable IMERG source does not meet the frozen contract."""


@dataclass(frozen=True)
class SourceInterval:
    path: Path
    start: datetime
    end: datetime


def utc_datetime(value: str) -> datetime:
    """Parse an ISO UTC timestamp."""
    return datetime.fromisoformat(value).astimezone(UTC)


def source_intervals(raw_directory: Path, expected_count: int = 240) -> list[SourceInterval]:
    """Enumerate and validate the frozen native IMERG files without writing Raw."""
    paths = sorted(raw_directory.glob("*.HDF5"))
    if len(paths) != expected_count:
        raise RainfallSourceError(f"Expected {expected_count} HDF5 files, found {len(paths)}")
    intervals = []
    for path in paths:
        match = FILENAME.match(path.name)
        if not match:
            raise RainfallSourceError(f"Unexpected IMERG filename: {path.name}")
        start = datetime.strptime(match["date"] + match["start"], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        intervals.append(SourceInterval(path, start, start + SOURCE_INTERVAL))
    intervals.sort(key=lambda item: item.start)
    for previous, current in pairwise(intervals):
        if current.start != previous.end:
            raise RainfallSourceError(f"Missing, duplicate, or unordered interval before {current.path.name}")
    return intervals


def native_cell_intersection_indices(lon_bounds: np.ndarray, lat_bounds: np.ndarray, context) -> tuple[np.ndarray, np.ndarray]:
    """Select every native cell whose WGS84 bounds intersect the frozen context."""
    selected = [
        (lon_index, lat_index)
        for lon_index, (left, right) in enumerate(lon_bounds)
        for lat_index, (bottom, top) in enumerate(lat_bounds)
        if box(float(left), float(bottom), float(right), float(top)).intersects(context)
    ]
    return (
        np.array(sorted({item[0] for item in selected}), dtype=int),
        np.array(sorted({item[1] for item in selected}), dtype=int),
    )

def normalized_time(interval_end: datetime) -> np.datetime64:
    """Return the end-labelled normalized timestamp for one source interval."""
    return np.datetime64(interval_end.replace(tzinfo=None))


def rate_to_depth(rate_mm_h: np.ndarray) -> np.ndarray:
    """Convert a half-hour precipitation rate field to interval depth in millimetres."""
    return rate_mm_h * 0.5


def trailing_complete(depth: xr.DataArray, intervals: int) -> xr.DataArray:
    """Sum only complete valid trailing windows; partial or missing windows stay null."""
    valid = xr.where(depth.notnull(), 1, 0)
    summed = depth.fillna(0).rolling(time=intervals, min_periods=intervals).sum()
    count = valid.rolling(time=intervals, min_periods=intervals).sum()
    return summed.where(count == intervals)


def event_total(depth: xr.DataArray, event_start: datetime, event_end: datetime) -> xr.DataArray:
    """Return a complete-only event total using source intervals [start, end)."""
    first_end = np.datetime64((event_start + SOURCE_INTERVAL).replace(tzinfo=None))
    final_end = np.datetime64(event_end.replace(tzinfo=None))
    selected = depth.sel(time=slice(first_end, final_end))
    expected = int((event_end - event_start) / SOURCE_INTERVAL)
    if selected.sizes["time"] != expected:
        raise RainfallSourceError(f"Expected {expected} event intervals, found {selected.sizes['time']}")
    return selected.sum("time", skipna=False)


def read_native_subset(intervals: list[SourceInterval], context) -> xr.Dataset:
    """Read a deterministic, bound-intersecting native-cell IMERG subset."""
    first = intervals[0]
    with h5py.File(first.path, "r") as source:
        grid = source["Grid"]
        lon = grid["lon"][:]
        lat = grid["lat"][:]
        lon_bounds = grid["lon_bnds"][:]
        lat_bounds = grid["lat_bnds"][:]
    lon_index, lat_index = native_cell_intersection_indices(lon_bounds, lat_bounds, context)
    if not len(lon_index) or not len(lat_index):
        raise RainfallSourceError("No native IMERG cell bounds intersect the acquisition context")
    fields = []
    starts = []
    ends = []
    for interval in intervals:
        with h5py.File(interval.path, "r") as source:
            grid = source["Grid"]
            header = dict(
                line.split("=", 1) for line in bytes(source.attrs["FileHeader"]).decode().splitlines() if "=" in line
            )
            source_start = utc_datetime(header["StartGranuleDateTime"].rstrip(";"))
            source_stop = utc_datetime(header["StopGranuleDateTime"].rstrip(";"))
            if source_start != interval.start or source_stop + timedelta(milliseconds=1) != interval.end:
                raise RainfallSourceError(f"Metadata time mismatch: {interval.path.name}")
            precipitation = grid["precipitation"]
            if precipitation.shape != (1, 3600, 1800) or bytes(precipitation.attrs["units"]).decode() != "mm/hr":
                raise RainfallSourceError(f"Unexpected precipitation structure: {interval.path.name}")
            fill = float(precipitation.attrs["_FillValue"])
            lon_slice = slice(int(lon_index.min()), int(lon_index.max()) + 1)
            lat_slice = slice(int(lat_index.min()), int(lat_index.max()) + 1)
            data = precipitation[0, lon_slice, lat_slice].T.astype("float32")
            data[data == fill] = np.nan
            fields.append(data)
            starts.append(np.datetime64(interval.start.replace(tzinfo=None)))
            ends.append(normalized_time(interval.end))
    rate = xr.DataArray(
        np.stack(fields), dims=("time", "lat", "lon"),
        coords={"time": ends, "lat": lat[lat_index], "lon": lon[lon_index]}, name="precipitation_rate_mm_h",
        attrs={"units": "mm/hr", "source_variable": "/Grid/precipitation", "missing_value_policy": "source fill converted to NaN"},
    )
    return xr.Dataset(
        {"precipitation_rate_mm_h": rate, "source_interval_start": ("time", starts), "source_interval_end": ("time", ends),
         "lat_bounds": (("lat", "bounds"), lat_bounds[lat_index]), "lon_bounds": (("lon", "bounds"), lon_bounds[lon_index])},
        attrs={"native_grid_resolution_degrees": 0.1, "spatial_subset_rule": "native_cell_bounds_intersect_frozen_2km_context"},
    )


def normalize_dataset(source: xr.Dataset, event_start: datetime, event_end: datetime) -> xr.Dataset:
    """Add depth, complete trailing accumulations, and complete-only event total."""
    rate = source["precipitation_rate_mm_h"]
    depth = rate_to_depth(rate).rename("precipitation_30m_mm")
    depth.attrs = {"units": "mm", "interval_hours": 0.5}
    result = source.assign(precipitation_30m_mm=depth)
    for label, intervals in (("1h", 2), ("3h", 6), ("6h", 12), ("24h", 48)):
        accumulation = trailing_complete(depth, intervals).rename(f"accumulation_{label}_mm")
        accumulation.attrs = {"units": "mm", "interval_count": intervals}
        result[accumulation.name] = accumulation
    total = event_total(depth, event_start, event_end).rename("event_total_mm")
    total.attrs = {"units": "mm", "interval_count": 144, "missing_data_policy": "all 144 intervals required"}
    result["event_total_mm"] = total
    result.attrs.update({
        "normalized_timestamp_convention": "time T represents [T - 30 minutes, T)",
        "rate_to_depth_conversion": "precipitation_30m_mm = precipitation_rate_mm_h * 0.5 h",
        "rolling_missing_data_policy": "complete window required; partial windows and source missing values are NaN",
        "event_interval_utc": f"[{event_start.isoformat().replace('+00:00', 'Z')}, {event_end.isoformat().replace('+00:00', 'Z')})",
        "native_information_content": "Native 0.1 degree cells retained; no resampling or downscaling.",
    })
    return result


def rainfall_lookup(dataset: xr.Dataset, timestamp: np.datetime64, longitude: float, latitude: float, window: str) -> dict[str, object]:
    """Return native-cell rainfall context for a timestamp and WGS84 point."""
    variables = {"30m": "precipitation_30m_mm", "1h": "accumulation_1h_mm", "3h": "accumulation_3h_mm", "6h": "accumulation_6h_mm", "24h": "accumulation_24h_mm"}
    if window not in variables:
        raise ValueError(f"Unsupported rainfall window: {window}")
    lon_match = np.where((dataset.lon_bounds[:, 0] <= longitude) & (longitude <= dataset.lon_bounds[:, 1]))[0]
    lat_match = np.where((dataset.lat_bounds[:, 0] <= latitude) & (latitude <= dataset.lat_bounds[:, 1]))[0]
    if len(lon_match) != 1 or len(lat_match) != 1:
        raise ValueError("Point is outside or ambiguous within the retained native IMERG cells")
    value = dataset[variables[window]].sel(time=timestamp).isel(lat=int(lat_match[0]), lon=int(lon_match[0])).item()
    return {"window": window, "value_mm": None if np.isnan(value) else float(value), "native_lon": float(dataset.lon.isel(lon=int(lon_match[0]))), "native_lat": float(dataset.lat.isel(lat=int(lat_match[0]))), "provenance": "native_imerg_context_no_downscaling"}
