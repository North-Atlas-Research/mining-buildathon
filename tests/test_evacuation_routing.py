import networkx as nx
from shapely.geometry import LineString, box

from mining_sprint.evacuation_routing import (
    ROUTE_PROVENANCE_NETWORK,
    deterministic_route_id,
    directed_graph,
    nearest_source_point,
    shortest_path,
    threshold_status,
)


def test_route_identity_is_deterministic_and_input_sensitive() -> None:
    first = deterministic_route_id("graph", "community-a", "shelter-b")
    assert first == deterministic_route_id("graph", "community-a", "shelter-b")
    assert first != deterministic_route_id("graph", "community-a", "shelter-c")


def test_directed_shortest_path_respects_one_way_and_length() -> None:
    graph = directed_graph(
        [
            {"from_node": 1, "to_node": 2, "edge_id": "a", "length_m": 3},
            {"from_node": 2, "to_node": 3, "edge_id": "b", "length_m": 4},
            {"from_node": 1, "to_node": 3, "edge_id": "c", "length_m": 20},
        ]
    )
    assert shortest_path(graph, 1, 3) == (["a", "b"], 7.0)
    assert shortest_path(graph, 3, 1) is None


def test_disconnected_route_returns_none() -> None:
    graph = nx.DiGraph()
    graph.add_edge(1, 2, edge_id="a", length_m=1.0)
    assert shortest_path(graph, 1, 9) is None


def test_connector_threshold_semantics() -> None:
    assert threshold_status(95.0) == (True, True, False)
    assert threshold_status(100.0) == (False, True, True)
    assert threshold_status(111.0) == (False, False, True)


def test_network_provenance_cannot_be_historical_evidence() -> None:
    assert ROUTE_PROVENANCE_NETWORK == "network_baseline"
    assert ROUTE_PROVENANCE_NETWORK not in {"historical_municipal_explicit", "community_plan_explicit"}


def test_polygon_connector_uses_nearest_boundary_not_representative_point() -> None:
    polygon = box(0, 0, 100, 100)
    edge = LineString([(100, 0), (100, 100)])
    anchor = nearest_source_point(polygon, edge)
    assert anchor.x == 100
    assert anchor.y == 0
    assert anchor != polygon.representative_point()
