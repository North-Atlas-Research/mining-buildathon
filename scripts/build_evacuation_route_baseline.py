"""Encode WS25-008 historical references and build a deterministic network baseline.

Historical sources are retained as reference/evaluation evidence only.  This script
does not claim an October 2020 official evacuation route and does not allocate
communities to shelters.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import nearest_points

from mining_sprint.evacuation_routing import (
    BASELINE_COST_POLICY,
    ROUTE_PROVENANCE_NETWORK,
    deterministic_route_id,
    directed_graph,
    nearest_source_point,
    normalize_road_name,
    shortest_path,
    threshold_status,
)

CRS = "EPSG:3448"
ROUTINE_SNAP_M = 95.0
OUTER_SNAP_M = 110.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def truth(value: object) -> bool:
    return str(value).strip().lower() == "true"


def nearest_attachment(geometry, edges: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame) -> dict:
    """Attach a source geometry at its nearest point on the nearest canonical edge.

    Polygon interiors are not presumed to be origin locations.  Using the closest
    point on the canonical geometry is the deterministic, geometry-faithful
    attachment; the selected endpoint remains a canonical OSM node.
    """
    distances = edges.geometry.distance(geometry)
    edge = edges.loc[distances.idxmin()]
    source_point = nearest_source_point(geometry, edge.geometry)
    _, edge_point = nearest_points(edge.geometry, geometry)
    node_rows = nodes.set_index("osm_node_id").loc[[edge.from_node, edge.to_node]]
    node_distances = node_rows.geometry.distance(edge_point)
    node_id = int(node_distances.sort_values(kind="stable").index[0])
    return {
        "graph_edge_id": edge.edge_id,
        "graph_node_id": node_id,
        "attachment_distance_m": float(distances.min()),
        "connector_geometry": LineString([source_point, node_rows.loc[node_id].geometry]),
    }


def undirected_components(graph: nx.DiGraph) -> dict[int, int]:
    return {
        node: index
        for index, component in enumerate(nx.connected_components(graph.to_undirected()))
        for node in component
    }


def source_road_rows(path: Path, provenance: str, route_col: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in csv.DictReader(path.open(encoding="utf-8")):
        ordered = row.get("road_sequence_ordered") or row["road_sequence_raw"]
        for ordinal, raw in enumerate(ordered.split("|"), 1):
            raw = raw.strip()
            if raw:
                rows.append(
                    {
                        "source_route_id": row[route_col],
                        "route_provenance": provenance,
                        "road_sequence_ordinal": str(ordinal),
                        "road_name_raw": raw,
                    }
                )
    return rows


def historical_matches(edges: gpd.GeoDataFrame, outputs: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    inputs = [
        (outputs / "source_b_route_inventory.csv", "historical_municipal_explicit", "route_id"),
        (outputs / "waterford_route_inventory.csv", "community_plan_explicit", "waterford_route_id"),
    ]
    source_rows = [item for path, provenance, key in inputs for item in source_road_rows(path, provenance, key)]
    indexed = edges.assign(_name_key=edges.name.map(normalize_road_name))
    records: list[dict[str, object]] = []
    for item in source_rows:
        key = normalize_road_name(item["road_name_raw"])
        candidates = indexed[indexed._name_key == key] if key else indexed.iloc[0:0]
        ways = sorted(set(candidates.osm_way_id.astype(int))) if len(candidates) else []
        status = "no_match" if not ways else "exact_match" if len(ways) == 1 else "multiple_candidates"
        selected = candidates[candidates.osm_way_id == ways[0]].iloc[0] if len(ways) == 1 else None
        records.append(
            {
                **item,
                "road_name_normalized": key,
                "graph_match_status": status,
                "candidate_count": len(ways),
                "selected_graph_name": selected["name"] if selected is not None else "",
                "selected_osm_way_id_if_applicable": int(selected.osm_way_id) if selected is not None else "",
                "notes": "Exact normalized graph-name comparison only; raw source spelling is retained.",
                "review_required": status != "exact_match",
            }
        )
    frame = pd.DataFrame(records)
    frame.to_csv(outputs / "historical_road_name_matches.csv", index=False)
    route_ids = sorted({row["source_route_id"] for row in records})
    review = pd.DataFrame(
        {
            "source_route_id": route_ids,
            "status": "unresolved",
            "reason": "Reference-only route reconstruction deferred: named-road matching alone does not establish endpoints, ordered graph segments, or a defensible directed path.",
            "route_provenance": [next(r["route_provenance"] for r in records if r["source_route_id"] == route_id) for route_id in route_ids],
        }
    )
    review.to_csv(outputs / "historical_route_reconstruction_review.csv", index=False)
    return frame, review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("/workspace/data"))
    args = parser.parse_args()
    root = args.data_root
    graph_path = root / "Processed/roads/portmore_road_graph_2020.gpkg"
    communities_path = root / "Processed/communities/portmore_community_zones_2020.gpkg"
    shelters_path = root / "Processed/shelters/portmore_shelters_2019.gpkg"
    outputs = root / "Outputs/ws25-008"
    processed = root / "Processed/evacuation"
    outputs.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    edges = gpd.read_file(graph_path, layer="portmore_road_edges_2020")
    nodes = gpd.read_file(graph_path, layer="portmore_road_nodes_2020")
    if len(edges) != 18046 or len(nodes) != 9571 or edges.crs.to_string() != CRS:
        raise SystemExit("WS25-007 graph contract does not match the frozen canonical input")
    graph = directed_graph(edges[["from_node", "to_node", "edge_id", "length_m"]].to_dict("records"))
    components = undirected_components(graph)
    graph_hash = sha256(graph_path)
    matches, historical_review = historical_matches(edges, outputs)
    communities = gpd.read_file(communities_path, layer="portmore_community_zones_2020")
    shelters = gpd.read_file(shelters_path, layer="portmore_shelters_2019")
    shelter_mask = shelters.geometry.notna() & shelters.in_acquisition_context_buffer.map(truth)
    shelters = shelters.loc[shelter_mask].copy()
    community_records = []
    connector_records = []
    for row in communities.itertuples():
        attached = nearest_attachment(row.geometry, edges, nodes)
        component = components.get(attached["graph_node_id"])
        record = {
            "community_id": row.community_id,
            "original_geometry_reference": f"{communities_path}#portmore_community_zones_2020",
            "graph_edge_id": attached["graph_edge_id"],
            "graph_node_id": attached["graph_node_id"],
            "attachment_method": "source_geometry_nearest_point_to_nearest_canonical_edge_then_nearest_endpoint",
            "attachment_distance_m": attached["attachment_distance_m"],
            "component_id": component,
            "review_required": row.community_name_normalized == "cromarty",
            "geometry": attached["connector_geometry"],
        }
        community_records.append(record)
        connector_records.append({**record, "connector_type": "community"})
    shelter_records = []
    for row in shelters.itertuples():
        attached = nearest_attachment(row.geometry, edges, nodes)
        routine, outer, review = threshold_status(attached["attachment_distance_m"])
        record = {
            "shelter_id": row.shelter_id,
            "original_geometry_reference": f"{shelters_path}#portmore_shelters_2019",
            "graph_edge_id": attached["graph_edge_id"],
            "graph_node_id": attached["graph_node_id"],
            "attachment_method": "point_to_nearest_canonical_edge_then_nearest_endpoint",
            "snap_distance_m": attached["attachment_distance_m"],
            "within_routine_threshold": routine,
            "within_outer_review_threshold": outer,
            "review_required": review,
            "component_id": components.get(attached["graph_node_id"]),
            "geometry": attached["connector_geometry"],
        }
        shelter_records.append(record)
        connector_records.append({**record, "connector_type": "shelter"})
    community_frame = gpd.GeoDataFrame(community_records, geometry="geometry", crs=CRS)
    shelter_frame = gpd.GeoDataFrame(shelter_records, geometry="geometry", crs=CRS)
    community_frame.drop(columns="geometry").to_csv(outputs / "community_graph_connectors.csv", index=False)
    shelter_frame.drop(columns="geometry").to_csv(outputs / "shelter_graph_connectors.csv", index=False)
    edge_lookup = edges.set_index("edge_id")
    matrix: list[dict[str, object]] = []
    route_records: list[dict[str, object]] = []
    for origin in community_records:
        for destination in shelter_records:
            result = shortest_path(graph, origin["graph_node_id"], destination["graph_node_id"])
            if result is None:
                reason = "different_components" if origin["component_id"] != destination["component_id"] else "no_directed_path"
                matrix.append({"community_id": origin["community_id"], "shelter_id": destination["shelter_id"], "origin_component": origin["component_id"], "shelter_component": destination["component_id"], "reachable": False, "network_distance_m": "", "edge_count": 0, "route_id_if_reachable": "", "failure_reason": reason})
                continue
            edge_ids, distance = result
            route_id = deterministic_route_id(graph_hash, origin["community_id"], destination["shelter_id"])
            geometries = [edge_lookup.loc[edge_id].geometry for edge_id in edge_ids]
            geometry = MultiLineString(geometries) if geometries else MultiLineString([])
            matrix.append({"community_id": origin["community_id"], "shelter_id": destination["shelter_id"], "origin_component": origin["component_id"], "shelter_component": destination["component_id"], "reachable": True, "network_distance_m": distance, "edge_count": len(edge_ids), "route_id_if_reachable": route_id, "failure_reason": ""})
            route_records.append({"route_id": route_id, "route_provenance": ROUTE_PROVENANCE_NETWORK, "official_route_status": "network-derived; not official; not confirmed event-day route", "origin_id": origin["community_id"], "destination_id": destination["shelter_id"], "graph_sha256": graph_hash, "baseline_cost_policy": BASELINE_COST_POLICY, "network_distance_m": distance, "edge_count": len(edge_ids), "edge_ids_json": json.dumps(edge_ids), "geometry": geometry})
    matrix_frame = pd.DataFrame(matrix)
    matrix_frame.to_csv(outputs / "community_shelter_routing_matrix.csv", index=False)
    routes = gpd.GeoDataFrame(route_records, geometry="geometry", crs=CRS)
    routes.drop(columns="geometry").to_csv(outputs / "network_baseline_routes.csv", index=False)
    gpkg = processed / "portmore_route_reference_and_baseline_2020.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    routes.to_file(gpkg, layer="network_baseline_routes", driver="GPKG")
    gpd.GeoDataFrame(connector_records, geometry="geometry", crs=CRS).to_file(gpkg, layer="route_connectors", driver="GPKG", mode="a")
    routes.to_crs("EPSG:4326").to_file(outputs / "route_preview_epsg4326.geojson", driver="GeoJSON")
    review = pd.DataFrame([
        {"review_id": "ws25-008-historical-reference", "category": "historical_route_reconstruction", "detail": "All historical routes remain reference-only and unresolved for graph reconstruction; no bridging geometry was invented."},
        {"review_id": "ws25-008-cromarty", "category": "component", "detail": "Cromarty attachment is retained; disconnected candidate pairs are reported without synthetic connectivity."},
    ])
    review.to_csv(outputs / "review_queue.csv", index=False)
    validation = {
        "graph": {"path": str(graph_path), "sha256": graph_hash, "directed_edges": len(edges), "nodes": len(nodes), "audit_edges_used": 0},
        "historical": {"road_name_matches": int((matches.graph_match_status == "exact_match").sum()), "ambiguous_or_unmatched": int((matches.graph_match_status != "exact_match").sum()), "municipal_routes_reconstructed": 0, "waterford_routes_reconstructed": 0, "review_records": len(historical_review)},
        "connectors": {"communities_attached": len(community_records), "shelters_attached": len(shelter_records), "shelters_within_95m": int(shelter_frame.within_routine_threshold.sum()), "shelters_95_to_110m": int((~shelter_frame.within_routine_threshold & shelter_frame.within_outer_review_threshold).sum()), "shelters_over_110m": int((~shelter_frame.within_outer_review_threshold).sum())},
        "routing": {"matrix_rows": len(matrix), "reachable": int(matrix_frame.reachable.sum()), "unreachable": int((~matrix_frame.reachable).sum()), "network_baseline_route_count": len(routes), "route_ids_unique": bool(routes.route_id.is_unique), "all_edge_ids_exist": all(set(json.loads(row.edge_ids_json)).issubset(set(edges.edge_id)) for row in routes.itertuples()), "cromarty_routes_reachable": int(matrix_frame.loc[matrix_frame.community_id == next(row["community_id"] for row in community_records if row["review_required"]), "reachable"].sum())},
        "scope": "Network-derived routes use projected metric length only and are not official evacuation routes.",
    }
    (outputs / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    (outputs / "lineage.json").write_text(json.dumps({"historical_sources": ["source_b_route_inventory.csv", "waterford_route_inventory.csv"], "graph": str(graph_path), "provenance_categories": ["historical_municipal_explicit", "community_plan_explicit", "network_baseline"], "excluded": ["rainfall", "flood accessibility", "road closures", "shelter allocation"]}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
