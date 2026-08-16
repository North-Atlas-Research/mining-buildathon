"""Deterministic, directed routing primitives for WS25-008.

These functions deliberately contain no claim about official evacuation policy.
They operate on the frozen WS25-007 graph using projected metric length only.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from itertools import pairwise

import networkx as nx
from shapely.ops import nearest_points

ROUTE_PROVENANCE_NETWORK = "network_baseline"
BASELINE_COST_POLICY = "projected_metric_road_length_m"


def normalize_road_name(value: str | None) -> str:
    """Create a conservative search key while retaining source text elsewhere."""
    if not value:
        return ""
    text = value.replace("%", " ").lower()
    text = re.sub(r"\b(street|st|road|rd|drive|dr|avenue|ave|boulevard|blvd)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def route_seed(graph_sha256: str, origin_id: str, destination_id: str) -> str:
    """Return the frozen, explicit seed for a network-baseline route."""
    return "|".join(
        (
            "WS25-008",
            f"graph_sha256={graph_sha256}",
            f"origin={origin_id}",
            f"destination={destination_id}",
            f"cost={BASELINE_COST_POLICY}",
        )
    )


def deterministic_route_id(graph_sha256: str, origin_id: str, destination_id: str) -> str:
    """Return a stable SHA-256 route identifier independent of processing order."""
    return "route_" + hashlib.sha256(route_seed(graph_sha256, origin_id, destination_id).encode()).hexdigest()


def directed_graph(edge_rows: Iterable[dict]) -> nx.DiGraph:
    """Build a directed graph retaining the canonical edge ID and metric cost."""
    graph = nx.DiGraph()
    for row in edge_rows:
        length = float(row["length_m"])
        if length <= 0:
            raise ValueError("Routing edges must have positive projected metric length")
        source, target = int(row["from_node"]), int(row["to_node"])
        prior = graph.get_edge_data(source, target)
        if prior is None or length < prior["length_m"] or (
            length == prior["length_m"] and str(row["edge_id"]) < prior["edge_id"]
        ):
            graph.add_edge(source, target, edge_id=str(row["edge_id"]), length_m=length)
    return graph


def shortest_path(graph: nx.DiGraph, origin: int, destination: int) -> tuple[list[str], float] | None:
    """Return canonical directed edge IDs and their length sum, or ``None``."""
    if origin not in graph or destination not in graph:
        return None
    try:
        nodes = nx.shortest_path(graph, origin, destination, weight="length_m")
    except nx.NetworkXNoPath:
        return None
    edge_ids = [graph[left][right]["edge_id"] for left, right in pairwise(nodes)]
    distance = sum(float(graph[left][right]["length_m"]) for left, right in pairwise(nodes))
    return edge_ids, distance


def nearest_source_point(source_geometry, edge_geometry):
    """Return the source-side nearest point; never substitute a polygon centroid."""
    return nearest_points(source_geometry, edge_geometry)[0]


def threshold_status(distance_m: float, routine_m: float = 95.0, outer_m: float = 110.0) -> tuple[bool, bool, bool]:
    """Return routine, outer, and review flags for a graph-specific snap diagnostic."""
    routine = distance_m <= routine_m
    outer = distance_m <= outer_m
    return routine, outer, not routine
