"""Build the approved WS25-007 event-era Portmore road graph.

The GeoPackage produced here is authoritative.  Native OSM memberships create
all graph topology; spatial operations are diagnostics only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).parent))
from compare_historical_osm_snapshots import build_candidate, sha256

TARGET_DATE = "2020-10-05"
SNAPSHOT_DATE = "2021-01-01"
SNAPSHOT = "jamaica-210101.osm.pbf"


def temporal_support(timestamp: str | None) -> tuple[str, int | None]:
    if timestamp is None:
        return "post_event_uncertain", None
    date = datetime.fromisoformat(timestamp).date()
    target = datetime.fromisoformat(f"{TARGET_DATE}T00:00:00+00:00").date()
    return ("event_supported" if date <= target else "post_event_uncertain"), (date - target).days


def component_flags(edges: gpd.GeoDataFrame, boundary_geometry) -> gpd.GeoDataFrame:
    graph = nx.Graph()
    graph.add_edges_from(zip(edges.from_osm_node_id, edges.to_osm_node_id))
    component = {
        node: index for index, nodes in enumerate(nx.connected_components(graph)) for node in nodes
    }
    operational_components = {
        component[row.from_osm_node_id]
        for row in edges.itertuples()
        if row.geometry.intersects(boundary_geometry)
    }
    edges["component_id"] = edges.from_osm_node_id.map(component)
    edges["external_connector"] = [
        (not geom.within(boundary_geometry)) and component[source] in operational_components
        for geom, source in zip(edges.geometry, edges.from_osm_node_id)
    ]
    return edges


def nodes_from_edges(edges: gpd.GeoDataFrame, boundary_geometry) -> gpd.GeoDataFrame:
    graph = nx.DiGraph()
    graph.add_edges_from(zip(edges.from_osm_node_id, edges.to_osm_node_id))
    undirected = graph.to_undirected()
    coordinates: dict[int, Point] = {}
    for row in edges.itertuples():
        coordinates.setdefault(row.from_osm_node_id, Point(row.geometry.coords[0]))
        coordinates.setdefault(row.to_osm_node_id, Point(row.geometry.coords[-1]))
    external = set(edges.loc[edges.external_connector, "from_osm_node_id"]) | set(
        edges.loc[edges.external_connector, "to_osm_node_id"]
    )
    records = [
        {
            "node_id": f"osm_node_{node}",
            "osm_node_id": node,
            "degree": undirected.degree(node),
            "inside_operational_boundary": point.within(boundary_geometry),
            "external_connector": node in external,
            "geometry": point,
        }
        for node, point in coordinates.items()
    ]
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:3448")


def diagnostics(edges: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame, context_geometry) -> dict:
    source = "from_node" if "from_node" in edges else "from_osm_node_id"
    target = "to_node" if "to_node" in edges else "to_osm_node_id"
    graph = nx.DiGraph()
    graph.add_edges_from(zip(edges[source], edges[target]))
    undirected = graph.to_undirected()
    components = list(nx.connected_components(undirected))
    largest = max(components, key=len) if components else set()
    touching = edges.intersects(context_geometry.boundary)
    return {
        "directed_edge_count": len(edges),
        "node_count": len(nodes),
        "unique_edge_ids": bool(edges.edge_id.is_unique),
        "unique_node_ids": bool(nodes.node_id.is_unique),
        "referential_integrity": bool(
            set(edges[source]).union(edges[target]).issubset(set(nodes.osm_node_id))
        ),
        "empty_edge_geometry_count": int(edges.geometry.is_empty.sum()),
        "invalid_edge_geometry_count": int((~edges.geometry.is_valid).sum()),
        "non_positive_length_count": int((edges.length_m <= 0).sum()),
        "oneway_directed_edge_count": int((edges.oneway != 0).sum()),
        "roundabout_directed_edge_count": int((edges.junction == "roundabout").sum()),
        "parallel_directed_edge_count": int(edges.duplicated([source, target]).sum()),
        "self_loop_count": int((edges[source] == edges[target]).sum()),
        "dangling_node_count": int(sum(degree == 1 for _, degree in undirected.degree())),
        "connected_component_count": len(components),
        "isolated_component_count": int(sum(len(c) == 1 for c in components)),
        "largest_component_node_percent": round(100 * len(largest) / len(nodes), 3)
        if len(nodes)
        else 0,
        "largest_component_edge_percent": round(
            100 * sum(a in largest and b in largest for a, b in graph.edges) / len(edges), 3
        )
        if len(edges)
        else 0,
        "acquisition_boundary_touching_directed_edge_count": int(touching.sum()),
        "acquisition_boundary_touching_component_count": len(
            set(edges.loc[touching, "component_id"])
        ),
        "external_connector_directed_edge_count": int(edges.external_connector.sum()),
        "highway_counts": dict(sorted(Counter(edges.highway).items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("/workspace/data"))
    args = parser.parse_args()
    root = args.data_root
    interim = root / "Interim" / "roads" / "ws25-007"
    processed = root / "Processed" / "roads"
    outputs = root / "Outputs" / "ws25-007"
    processed.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    boundary = gpd.read_file(
        root / "Processed/region/portmore_boundary.gpkg", layer="portmore_jamaica_2020"
    )
    context = gpd.read_file(root / "Interim/region/portmore_acquisition_context_buffer_2000m.gpkg")
    context_4326 = interim / "portmore_acquisition_context_2000m_epsg4326.geojson"
    raw = root / "Raw" / SNAPSHOT
    all_edges, _candidate_stats, _ = build_candidate(
        SNAPSHOT_DATE, raw, context_4326, boundary, interim
    )
    support = (
        all_edges.osm_timestamp if "osm_timestamp" in all_edges else all_edges.source_timestamp
    )
    all_edges["osm_timestamp"] = support
    classes = all_edges.osm_timestamp.map(temporal_support)
    all_edges["temporal_support_class"] = classes.map(lambda value: value[0])
    all_edges["temporal_offset_days"] = classes.map(lambda value: value[1])
    all_edges["source_snapshot"] = SNAPSHOT
    all_edges["source_snapshot_date"] = SNAPSHOT_DATE
    all_edges["source_snapshot_sha256"] = sha256(raw)
    all_edges["target_event_date"] = TARGET_DATE
    all_edges["historical_approximation"] = "2020-era historical road-network approximation"
    all_edges["access_restricted"] = all_edges.access_status == "restricted_included"
    all_edges["known_uncertainty"] = np.where(
        all_edges.temporal_support_class == "post_event_uncertain",
        "Represented OSM way timestamp is after the target event date; preserved in audit layer only.",
        "OSM mapping state is not a claim of exact event-day physical or operational road conditions.",
    )
    all_edges = component_flags(all_edges, boundary.iloc[0].geometry)
    audit = all_edges[all_edges.temporal_support_class == "post_event_uncertain"].copy()
    edges = all_edges[all_edges.temporal_support_class == "event_supported"].copy()
    nodes = nodes_from_edges(edges, boundary.iloc[0].geometry)
    required = [
        "edge_id",
        "from_node",
        "to_node",
        "osm_way_id",
        "osm_version",
        "osm_timestamp",
        "source_snapshot",
        "source_snapshot_date",
        "source_snapshot_sha256",
        "target_event_date",
        "temporal_offset_days",
        "temporal_support_class",
        "historical_approximation",
        "highway",
        "name",
        "ref",
        "oneway",
        "maxspeed",
        "lanes",
        "bridge",
        "tunnel",
        "surface",
        "access",
        "motor_vehicle",
        "vehicle",
        "service",
        "junction",
        "access_restricted",
        "access_assumption",
        "length_m",
        "inside_operational_boundary",
        "crosses_operational_boundary",
        "external_connector",
        "known_uncertainty",
        "geometry",
    ]
    for field in (
        "maxspeed",
        "lanes",
        "bridge",
        "tunnel",
        "surface",
        "access",
        "motor_vehicle",
        "vehicle",
    ):
        if field not in edges:
            edges[field] = edges.tags_json.map(
                lambda value, field=field: json.loads(value).get(field)
            )
    edges = edges.rename(columns={"from_osm_node_id": "from_node", "to_osm_node_id": "to_node"})
    graph_path = processed / "portmore_road_graph_2020.gpkg"
    temporary = processed / "portmore_road_graph_2020.tmp.gpkg"
    if temporary.exists():
        temporary.unlink()
    edges[required].to_file(temporary, layer="portmore_road_edges_2020", driver="GPKG")
    nodes.to_file(temporary, layer="portmore_road_nodes_2020", driver="GPKG", mode="a")
    os.replace(temporary, graph_path)
    if os.environ.get("WS25_007_GRAPH_ONLY") == "1":
        return
    validation = diagnostics(edges, nodes, context.iloc[0].geometry)
    shelters = gpd.read_file(
        root / "Processed/shelters/portmore_shelters_2019.gpkg", layer="portmore_shelters_2019"
    )
    accepted = shelters.dropna(subset=["geometry"]).copy()
    accepted["nearest_road_m"] = [edges.distance(point).min() for point in accepted.geometry]
    accepted_in_context = accepted[accepted.intersects(context.iloc[0].geometry)].copy()
    accepted_outside_context_count = len(accepted) - len(accepted_in_context)
    accepted = accepted_in_context
    distances = accepted.nearest_road_m
    snap = {
        "count": len(distances),
        "accepted_outside_acquisition_context_count": accepted_outside_context_count,
        "min_m": float(distances.min()),
        "median_m": float(distances.median()),
        "p95_m": float(distances.quantile(0.95)),
        "max_m": float(distances.max()),
        "proposed_routine_snap_threshold_m": float(np.ceil(distances.quantile(0.95) / 5) * 5),
        "proposed_outer_review_threshold_m": float(np.ceil(distances.max() / 5) * 5),
    }
    communities = gpd.read_file(
        root / "Processed/communities/portmore_community_zones_2020.gpkg",
        layer="portmore_community_zones_2020",
    )
    communities["nearest_road_m"] = [edges.distance(geom).min() for geom in communities.geometry]
    coverage = {row.community_name: float(row.nearest_road_m) for row in communities.itertuples()}
    review_rows = [
        {
            "review_type": "post_event_edge",
            "identifier": row.edge_id,
            "detail": row.known_uncertainty,
        }
        for row in audit.itertuples()
    ]
    review_rows += [
        {
            "review_type": "community_coverage",
            "identifier": name,
            "detail": f"nearest eligible road {distance:.2f} m",
        }
        for name, distance in coverage.items()
        if distance > 100
    ]
    gpd.GeoDataFrame(edges, geometry="geometry", crs="EPSG:3448").to_crs("EPSG:4326").to_file(
        outputs / "road_graph_preview_epsg4326.geojson", driver="GeoJSON"
    )
    with (outputs / "review_queue.csv").open("w", encoding="utf-8", newline="") as stream:
        import csv

        writer = csv.DictWriter(stream, fieldnames=["review_type", "identifier", "detail"])
        writer.writeheader()
        writer.writerows(review_rows)
    validation.update(
        {
            "event_supported_routable_directed_edge_count": len(edges),
            "post_event_audit_only_directed_edge_count": len(audit),
            "shelter_nearest_road_distance_m": snap,
            "community_nearest_road_m": coverage,
        }
    )
    (outputs / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    lineage = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "canonical_source_decision": "Recommendation A",
        "raw_source": {"path": str(raw), "sha256": sha256(raw)},
        "extent": "frozen operational boundary + 2000 m acquisition context",
        "crs": "EPSG:3448",
        "topology": "consecutive native OSM way node memberships only; no geometric-intersection links",
        "road_policy": "approved highway/access/direction policy",
        "temporal_policy": "event_supported edges routable; post_event_uncertain edges audit-only",
        "identity": "SHA-256 of frozen versioned edge seed",
        "known_uncertainty": "2020-era OSM approximation, not event-day physical/operational road state",
    }
    (outputs / "lineage.json").write_text(json.dumps(lineage, indent=2) + "\n")


if __name__ == "__main__":
    main()
