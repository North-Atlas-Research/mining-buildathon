"""Create WS25-007 candidate-network and comparison diagnostics.

This is intentionally an inspection-stage script: it never writes a canonical
Processed graph.  OSM topology comes exclusively from consecutive native node
memberships of each way; geometric intersections are not used to create links.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString

INCLUDED_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
}
CONDITIONAL_HIGHWAYS = {"service", "track"}
EXCLUDED_HIGHWAYS = {"pedestrian", "footway", "cycleway", "path", "construction", "proposed"}
EXCLUDED_ACCESS = {"no", "private"}
RESTRICTED_ACCESS = {"destination", "permissive"}
TRUE_ONEWAY = {"yes", "true", "1"}
WAY_RE = re.compile(r"^w(?P<id>\d+)\b")
NODE_RE = re.compile(r"^n(?P<id>\d+)\b")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def opl_tags(value: str) -> dict[str, str]:
    if not value or value == "T":
        return {}
    return {
        unquote(pair.split("=", 1)[0]): unquote(pair.split("=", 1)[1])
        for pair in value[1:].split(",")
        if "=" in pair
    }


def parse_opl(path: Path) -> tuple[dict[int, tuple[float, float]], list[dict[str, object]]]:
    """Read OPL emitted by osmium; preserves ordered ``Nn…`` way members."""
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            fields = line.rstrip("\n").split(" ")
            if not fields:
                continue
            if fields[0].startswith("n"):
                match = NODE_RE.match(fields[0])
                values = {
                    item[0]: item[1:] for item in fields[1:] if item and item[0] in {"x", "y"}
                }
                if match and "x" in values and "y" in values:
                    nodes[int(match["id"])] = (float(values["x"]), float(values["y"]))
            elif fields[0].startswith("w"):
                match = WAY_RE.match(fields[0])
                values = {item[0]: item[1:] for item in fields[1:] if item}
                refs = [
                    int(ref[1:]) for ref in values.get("N", "").split(",") if ref.startswith("n")
                ]
                ways.append(
                    {
                        "osm_way_id": int(match["id"]),
                        "osm_version": int(values["v"]) if values.get("v", "").isdigit() else None,
                        "source_timestamp": values.get("t") or None,
                        "tags": opl_tags(values.get("T", "")),
                        "node_ids": refs,
                    }
                )
    return nodes, ways


def access_decision(tags: dict[str, str]) -> tuple[str, str, str | None]:
    """Apply frozen motor_vehicle -> vehicle -> access precedence."""
    source = next((key for key in ("motor_vehicle", "vehicle", "access") if key in tags), None)
    value = tags.get(source, "").lower() if source else ""
    if value in EXCLUDED_ACCESS:
        return "excluded", "not_applicable", source
    if value in RESTRICTED_ACCESS:
        return (
            "restricted_included",
            "review_required" if value == "permissive" else "known",
            source,
        )
    return "included", "unknown_default" if source is None else "known", source


def highway_decision(tags: dict[str, str]) -> tuple[bool, str]:
    highway = tags.get("highway")
    if highway in INCLUDED_HIGHWAYS:
        return True, "included"
    if highway == "service":
        return True, "conditional_service"
    if highway == "track":
        affirmative = tags.get("motor_vehicle", "").lower() in {"yes", "designated", "permissive"}
        blocked = tags.get("construction") == "yes" or tags.get("proposed") == "yes"
        return (
            affirmative and not blocked,
            "conditional_track"
            if affirmative and not blocked
            else "track_requires_affirmative_motor_vehicle_access",
        )
    if highway in EXCLUDED_HIGHWAYS:
        return False, f"excluded_{highway}"
    return False, "missing_or_unfamiliar_highway"


def oneway(tags: dict[str, str]) -> int:
    value = tags.get("oneway", "").lower()
    if value == "-1":
        return -1
    if value in TRUE_ONEWAY or tags.get("junction", "").lower() == "roundabout":
        return 1
    return 0


def edge_identifier(
    snapshot_sha: str,
    way_id: int,
    version: int,
    source: int,
    target: int,
    ordinal: int,
    direction: str,
) -> str:
    seed = (
        f"ws25-007|{snapshot_sha}|way|{way_id}|version|{version}|from|{source}|"
        f"to|{target}|segment|{ordinal}|direction|{direction}"
    )
    return hashlib.sha256(seed.encode()).hexdigest()


def build_candidate(
    snapshot: str, raw: Path, context_4326: Path, boundary, output_dir: Path
) -> tuple[gpd.GeoDataFrame, dict, list[dict[str, object]]]:
    extract = output_dir / f"{snapshot}_acquisition_context.osm.pbf"
    opl = output_dir / f"{snapshot}_acquisition_context.opl"
    run(
        [
            "osmium",
            "extract",
            "--polygon",
            str(context_4326),
            "--strategy",
            "complete_ways",
            "--set-bounds",
            "--output",
            str(extract),
            "--overwrite",
            str(raw),
        ]
    )
    run(
        [
            "osmium",
            "cat",
            "--object-type",
            "node",
            "--object-type",
            "way",
            "--output-format",
            "opl",
            "--output",
            str(opl),
            "--overwrite",
            str(extract),
        ]
    )
    nodes, ways = parse_opl(opl)
    source_sha = sha256(raw)
    excluded_classes: Counter[str] = Counter()
    access_exclusions: Counter[str] = Counter()
    included_classes: Counter[str] = Counter()
    rows: list[dict[str, object]] = []
    eligible_ways: list[dict[str, object]] = []
    for way in ways:
        tags = way["tags"]
        highway = tags.get("highway")
        highway_included, highway_reason = highway_decision(tags)
        if not highway_included:
            excluded_classes[highway_reason] += 1
            continue
        status, access_assumption, access_source = access_decision(tags)
        if status == "excluded":
            access_exclusions[
                next(
                    (
                        f"{k}={tags[k]}"
                        for k in ("access", "vehicle", "motor_vehicle")
                        if tags.get(k, "").lower() in EXCLUDED_ACCESS
                    ),
                    "unknown",
                )
            ] += 1
            continue
        refs = way["node_ids"]
        if len(refs) < 2 or any(node not in nodes for node in refs):
            excluded_classes["missing_native_node_coordinate"] += 1
            continue
        included_classes[highway or "missing"] += 1
        eligible_ways.append(way)
        directionality = oneway(tags)
        segments = list(enumerate(itertools.pairwise(refs)))
        if directionality == -1:
            segments = [(ordinal, (target, source)) for ordinal, (source, target) in segments]
        directions = (
            [("forward", segments)]
            if directionality
            else [
                ("forward", segments),
                (
                    "reverse",
                    [(ordinal, (target, source)) for ordinal, (source, target) in segments],
                ),
            ]
        )
        for direction, directed_segments in directions:
            for ordinal, (source, target) in directed_segments:
                geometry = LineString([nodes[source], nodes[target]])
                rows.append(
                    {
                        "edge_id": edge_identifier(
                            source_sha,
                            way["osm_way_id"],
                            way["osm_version"],
                            source,
                            target,
                            ordinal,
                            direction,
                        ),
                        "comparison_key": f"way|{way['osm_way_id']}|from|{source}|to|{target}",
                        "topology_key": f"way|{way['osm_way_id']}|nodes|{'|'.join(map(str, sorted((source, target))))}",
                        "snapshot": snapshot,
                        "osm_way_id": way["osm_way_id"],
                        "osm_version": way["osm_version"],
                        "source_timestamp": way["source_timestamp"],
                        "from_osm_node_id": source,
                        "to_osm_node_id": target,
                        "segment_ordinal": ordinal,
                        "direction": direction,
                        "highway": highway,
                        "access_status": status,
                        "access_assumption": access_assumption,
                        "access_source": access_source,
                        "routing_policy_class": highway_reason,
                        "oneway": directionality,
                        "name": tags.get("name"),
                        "ref": tags.get("ref"),
                        "service": tags.get("service"),
                        "junction": tags.get("junction"),
                        "tags_json": json.dumps(tags, sort_keys=True),
                        "geometry": geometry,
                    }
                )
    edges = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:3448")
    edges["length_m"] = edges.length
    edges["inside_operational_boundary"] = edges.within(boundary.iloc[0].geometry)
    edges["crosses_operational_boundary"] = edges.intersects(boundary.iloc[0].geometry.boundary)
    graph = nx.DiGraph()
    graph.add_edges_from(zip(edges.from_osm_node_id, edges.to_osm_node_id))
    undirected = graph.to_undirected()
    components = list(nx.connected_components(undirected))
    largest = max(components, key=len) if components else set()
    degree = dict(undirected.degree())
    diagnostics = {
        "snapshot": snapshot,
        "raw_path": str(raw),
        "raw_sha256": source_sha,
        "candidate_way_count": len(eligible_ways),
        "node_count": graph.number_of_nodes(),
        "directed_edge_count": len(edges),
        "included_highway_way_counts": dict(sorted(included_classes.items())),
        "excluded_or_review_highway_way_counts": dict(sorted(excluded_classes.items())),
        "access_exclusions": dict(sorted(access_exclusions.items())),
        "oneway_way_count": sum(oneway(way["tags"]) != 0 for way in eligible_ways),
        "connected_component_count": len(components),
        "largest_component_node_percent": round(100 * len(largest) / graph.number_of_nodes(), 3)
        if graph
        else 0,
        "largest_component_edge_percent": round(
            100
            * sum(1 for a, b in graph.edges if a in largest and b in largest)
            / graph.number_of_edges(),
            3,
        )
        if graph
        else 0,
        "dangling_node_count": sum(value == 1 for value in degree.values()),
        "self_loop_count": sum(a == b for a, b in graph.edges),
        "parallel_edge_count": int(edges.duplicated(["from_osm_node_id", "to_osm_node_id"]).sum()),
        "native_way_version_metadata_available": all(
            way["osm_version"] is not None for way in eligible_ways
        ),
        "native_way_timestamp_metadata_available": all(
            way["source_timestamp"] is not None for way in eligible_ways
        ),
    }
    return edges, diagnostics, eligible_ways


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("/workspace/data"))
    args = parser.parse_args()
    root = args.data_root
    interim = root / "Interim" / "roads" / "ws25-007"
    outputs = root / "Outputs" / "ws25-007"
    interim.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    boundary = gpd.read_file(
        root / "Processed/region/portmore_boundary.gpkg", layer="portmore_jamaica_2020"
    )
    context = gpd.read_file(
        root / "Interim/region/portmore_acquisition_context_buffer_2000m.gpkg"
    ).to_crs("EPSG:4326")
    context_path = interim / "portmore_acquisition_context_2000m_epsg4326.geojson"
    context.to_file(context_path, driver="GeoJSON")
    snapshots = {
        "2019-01-01": root / "Raw/jamaica-190101.osm.pbf",
        "2021-01-01": root / "Raw/jamaica-210101.osm.pbf",
    }
    results = {
        name: build_candidate(name, raw, context_path, boundary, interim)
        for name, raw in snapshots.items()
    }
    old, new = results["2019-01-01"][0], results["2021-01-01"][0]
    old_keys, new_keys = set(old.comparison_key), set(new.comparison_key)
    rows = []
    for key in sorted(old_keys | new_keys):
        left, right = old[old.comparison_key == key], new[new.comparison_key == key]
        if not left.empty and not right.empty:
            status = (
                "persistent"
                if int(left.iloc[0].osm_version) == int(right.iloc[0].osm_version)
                else "version_changed"
            )
        elif not left.empty:
            status = "absent_by_2021"
        else:
            status = "added_by_2021"
        sample = (right if not right.empty else left).iloc[0]
        rows.append(
            {
                "comparison_key": key,
                "status": status,
                "osm_way_id": sample.osm_way_id,
                "from_osm_node_id": sample.from_osm_node_id,
                "to_osm_node_id": sample.to_osm_node_id,
                "highway": sample.highway,
                "geometry": sample.geometry,
            }
        )
    comparison = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:3448")
    comparison.to_file(
        outputs / "cross_snapshot_edge_comparison.gpkg", layer="comparison", driver="GPKG"
    )
    # Native sequence comparison classifies node insertions / changed segmentation before spatial heuristics.
    old_ways = {way["osm_way_id"]: way for way in results["2019-01-01"][2]}
    new_ways = {way["osm_way_id"]: way for way in results["2021-01-01"][2]}
    way_changes = []
    for way_id in sorted(set(old_ways) | set(new_ways)):
        left, right = old_ways.get(way_id), new_ways.get(way_id)
        if not left:
            kind = "added_by_2021"
        elif not right:
            kind = "absent_by_2021"
        elif left["node_ids"] == right["node_ids"] and left["tags"] == right["tags"]:
            kind = (
                "persistent" if left["osm_version"] == right["osm_version"] else "version_changed"
            )
        elif set(left["node_ids"]).issubset(set(right["node_ids"])):
            kind = "node_insertion_or_changed_segmentation"
        elif set(right["node_ids"]).issubset(set(left["node_ids"])):
            kind = "node_removal_or_changed_segmentation"
        elif left["node_ids"] == list(reversed(right["node_ids"])):
            kind = "direction_reversal"
        elif left["tags"].get("highway") != right["tags"].get("highway"):
            kind = "highway_class_changed"
        elif any(
            left["tags"].get(k) != right["tags"].get(k)
            for k in ("access", "vehicle", "motor_vehicle")
        ):
            kind = "access_changed"
        elif oneway(left["tags"]) != oneway(right["tags"]):
            kind = "direction_changed"
        else:
            kind = "topology_changed_or_uncertain_correspondence"
        way_changes.append(
            {
                "osm_way_id": way_id,
                "classification": kind,
                "old_version": left and left["osm_version"],
                "new_version": right and right["osm_version"],
                "old_node_count": left and len(left["node_ids"]),
                "new_node_count": right and len(right["node_ids"]),
            }
        )
    with (outputs / "way_change_classification.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(way_changes[0]))
        writer.writeheader()
        writer.writerows(way_changes)
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "tooling": {"osmium_command": "osmium", "required_native_topology": True},
        "identity_contract": "ws25-007|<source_snapshot_sha256>|way|<osm_way_id>|version|<osm_version>|from|<from_osm_node_id>|to|<to_osm_node_id>|segment|<segment_ordinal>|direction|<forward_or_reverse>; SHA-256 hex",
        "snapshots": {key: value[1] for key, value in results.items()},
        "edge_comparison_status_counts": dict(Counter(comparison.status)),
        "way_change_classification_counts": dict(
            Counter(row["classification"] for row in way_changes)
        ),
        "limitations": [
            "Split/merge correspondence is not asserted from matching geometry alone.",
            "No geometric line intersection creates topology.",
            "Candidate diagnostics are not a canonical Processed graph.",
        ],
    }
    (outputs / "comparison_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
