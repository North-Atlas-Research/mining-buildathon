"""Deterministic accessibility-aware route validation and minimal replanning."""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from math import inf

from mining_sprint.accessibility_state import (
    AccessibilityDecision,
    AccessibilityState,
    routing_semantics,
)


@dataclass(frozen=True)
class ShelterOption:
    """A candidate shelter attachment and explicit available capacity."""

    shelter_id: str
    node_id: int
    capacity_available: int
    capacity_provenance: str


@dataclass(frozen=True)
class RouteResult:
    """A deterministic state-aware path with physical distance and routing cost."""

    edge_ids: tuple[str, ...]
    distance_m: float
    routing_cost_m: float


@dataclass(frozen=True)
class ReplanningResult:
    """Structured result for one baseline assignment under stated edge states."""

    replay_timestamp: str
    community_id: str
    demand_people: int
    baseline_shelter_id: str
    baseline_route_id: str
    triggering_road_segment: str
    triggering_accessibility_state: AccessibilityState
    baseline_plan_status: str
    replanning_required: bool
    selected_shelter_id: str | None
    selected_route: RouteResult | None
    capacity_required: int
    capacity_available: int | None
    capacity_remaining: int | None
    decision_status: str
    reason_codes: tuple[str, ...]
    evidence: dict[str, object]
    provenance: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a machine-readable record without dropping audit evidence."""
        result = asdict(self)
        if self.selected_route is not None:
            result["selected_route"] = asdict(self.selected_route)
        result["reason_codes"] = list(self.reason_codes)
        result["provenance"] = list(self.provenance)
        return result


def state_for_edge(edge_id: str, decisions: dict[str, AccessibilityDecision]) -> AccessibilityState:
    """Use explicit WS25-010 decisions where supplied; otherwise retain open default."""
    return decisions[edge_id].state if edge_id in decisions else "open"


def route_status(
    edge_ids: Iterable[str], decisions: dict[str, AccessibilityDecision]
) -> tuple[bool, list[str], list[str]]:
    """Return traversability, unusable edges, and traversable concern-edge IDs."""
    unusable: list[str] = []
    concern: list[str] = []
    for edge_id in edge_ids:
        state = state_for_edge(edge_id, decisions)
        semantics = routing_semantics(state)
        if not semantics["usable"]:
            unusable.append(edge_id)
        elif semantics["review_required"]:
            concern.append(edge_id)
    return not unusable, unusable, concern


def _accessible_adjacency(
    edge_rows: Iterable[dict[str, object]], decisions: dict[str, AccessibilityDecision]
) -> dict[int, list[tuple[int, str, float, float]]]:
    """Build adjacency excluding unusable states and retaining deterministic costs."""
    adjacency: dict[int, list[tuple[int, str, float, float]]] = {}
    for row in edge_rows:
        edge_id = str(row["edge_id"])
        semantics = routing_semantics(state_for_edge(edge_id, decisions))
        if not semantics["usable"]:
            continue
        distance = float(row["length_m"])
        if distance <= 0:
            raise ValueError("Routing edges must have positive projected metric length")
        multiplier = float(semantics["cost_multiplier"])
        adjacency.setdefault(int(row["from_node"]), []).append(
            (int(row["to_node"]), edge_id, distance, distance * multiplier)
        )
    for choices in adjacency.values():
        choices.sort(key=lambda choice: (choice[1], choice[0]))
    return adjacency


def shortest_accessible_path(
    edge_rows: Iterable[dict[str, object]],
    decisions: dict[str, AccessibilityDecision],
    origin_node: int,
    destination_node: int,
) -> RouteResult | None:
    """Find the lowest deterministic cost path while excluding closed edges.

    Equal-cost paths are resolved by lexicographic edge-ID sequence, not graph
    iteration order. Physical distance stays separate from policy-weighted cost.
    """
    adjacency = _accessible_adjacency(edge_rows, decisions)
    queue: list[tuple[float, tuple[str, ...], float, int]] = [(0.0, (), 0.0, origin_node)]
    best: dict[int, tuple[float, tuple[str, ...]]] = {origin_node: (0.0, ())}
    while queue:
        cost, edge_ids, distance, node = heapq.heappop(queue)
        if best.get(node) != (cost, edge_ids):
            continue
        if node == destination_node:
            return RouteResult(edge_ids, distance, cost)
        for target, edge_id, edge_distance, edge_cost in adjacency.get(node, []):
            candidate = (cost + edge_cost, (*edge_ids, edge_id))
            if candidate < best.get(target, (inf, ())):
                best[target] = candidate
                heapq.heappush(
                    queue, (candidate[0], candidate[1], distance + edge_distance, target)
                )
    return None


def replan_assignment(
    *,
    replay_timestamp: str,
    community_id: str,
    demand_people: int,
    baseline_shelter_id: str,
    baseline_route_id: str,
    baseline_route_edges: Iterable[str],
    origin_node: int,
    shelters: Iterable[ShelterOption],
    edge_rows: Iterable[dict[str, object]],
    decisions: dict[str, AccessibilityDecision],
    triggering_road_segment: str,
) -> ReplanningResult:
    """Apply baseline validation, same-shelter reroute, then reassignment."""
    if demand_people <= 0:
        raise ValueError("Demand must be positive")
    shelters_by_id = {shelter.shelter_id: shelter for shelter in shelters}
    if baseline_shelter_id not in shelters_by_id:
        raise ValueError("Baseline shelter must be included among candidate shelters")
    graph_edges = tuple(edge_rows)
    baseline_edges = tuple(baseline_route_edges)
    usable, invalid_edges, concern_edges = route_status(baseline_edges, decisions)
    trigger_state = state_for_edge(triggering_road_segment, decisions)
    common = {
        "replay_timestamp": replay_timestamp,
        "community_id": community_id,
        "demand_people": demand_people,
        "baseline_shelter_id": baseline_shelter_id,
        "baseline_route_id": baseline_route_id,
        "triggering_road_segment": triggering_road_segment,
        "triggering_accessibility_state": trigger_state,
        "capacity_required": demand_people,
        "evidence": {
            "invalid_baseline_edges": invalid_edges,
            "baseline_concern_edges": concern_edges,
            "trigger_decision": decisions.get(triggering_road_segment).as_dict()
            if triggering_road_segment in decisions
            else None,
        },
        "provenance": ("ws25_010_accessibility_state", "frozen_ws25_007_008_graph"),
    }
    baseline_shelter = shelters_by_id[baseline_shelter_id]
    if usable:
        return ReplanningResult(
            **common,
            baseline_plan_status="valid",
            replanning_required=False,
            selected_shelter_id=baseline_shelter_id,
            selected_route=None,
            capacity_available=baseline_shelter.capacity_available,
            capacity_remaining=baseline_shelter.capacity_available - demand_people,
            decision_status="baseline_preserved",
            reason_codes=("baseline_route_all_edges_traversable",),
        )

    same_shelter = shortest_accessible_path(
        graph_edges, decisions, origin_node, baseline_shelter.node_id
    )
    if same_shelter is not None and baseline_shelter.capacity_available >= demand_people:
        return ReplanningResult(
            **common,
            baseline_plan_status="invalid_closed_edge",
            replanning_required=True,
            selected_shelter_id=baseline_shelter_id,
            selected_route=same_shelter,
            capacity_available=baseline_shelter.capacity_available,
            capacity_remaining=baseline_shelter.capacity_available - demand_people,
            decision_status="rerouted_same_shelter",
            reason_codes=("baseline_route_contains_unusable_edge", "same_shelter_reroute_selected"),
        )

    alternatives: list[tuple[float, str, ShelterOption, RouteResult]] = []
    capacity_rejected = False
    for shelter in shelters_by_id.values():
        if shelter.shelter_id == baseline_shelter_id:
            continue
        route = shortest_accessible_path(graph_edges, decisions, origin_node, shelter.node_id)
        if route is None:
            continue
        if shelter.capacity_available < demand_people:
            capacity_rejected = True
            continue
        alternatives.append((route.routing_cost_m, shelter.shelter_id, shelter, route))
    if alternatives:
        _, _, shelter, route = min(alternatives)
        return ReplanningResult(
            **common,
            baseline_plan_status="invalid_closed_edge",
            replanning_required=True,
            selected_shelter_id=shelter.shelter_id,
            selected_route=route,
            capacity_available=shelter.capacity_available,
            capacity_remaining=shelter.capacity_available - demand_people,
            decision_status="reassigned_alternative_shelter",
            reason_codes=(
                "baseline_route_contains_unusable_edge",
                "alternative_shelter_selected_by_cost_then_id",
            ),
        )
    reasons = ["baseline_route_contains_unusable_edge", "no_reachable_capacity_feasible_shelter"]
    if same_shelter is None:
        reasons.append("baseline_shelter_unreachable")
    elif baseline_shelter.capacity_available < demand_people:
        reasons.append("baseline_shelter_insufficient_capacity")
    if capacity_rejected:
        reasons.append("alternative_shelter_insufficient_capacity")
    return ReplanningResult(
        **common,
        baseline_plan_status="invalid_closed_edge",
        replanning_required=True,
        selected_shelter_id=None,
        selected_route=None,
        capacity_available=None,
        capacity_remaining=None,
        decision_status="no_feasible_plan",
        reason_codes=tuple(reasons),
    )
