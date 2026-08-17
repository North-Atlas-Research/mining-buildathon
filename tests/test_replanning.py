from mining_sprint.accessibility_state import ScenarioContext, evaluate_accessibility
from mining_sprint.replanning import (
    ShelterOption,
    replan_assignment,
    route_status,
    shortest_accessible_path,
)

EDGES = [
    {"from_node": 1, "to_node": 2, "edge_id": "a", "length_m": 1},
    {"from_node": 2, "to_node": 4, "edge_id": "b", "length_m": 1},
    {"from_node": 1, "to_node": 3, "edge_id": "c", "length_m": 2},
    {"from_node": 3, "to_node": 4, "edge_id": "d", "length_m": 2},
    {"from_node": 1, "to_node": 5, "edge_id": "e", "length_m": 3},
]
CTX = ScenarioContext("scenario_assumption", "test context", True)


def closed():
    return evaluate_accessibility(
        edge_id="b",
        timestamp="t",
        rainfall_3h_mm=14,
        rainfall_6h_mm=28,
        context=CTX,
        observation_status="confirmed_closed",
    )


def plan(shelters, decisions=None):
    return replan_assignment(
        replay_timestamp="t",
        community_id="c",
        demand_people=5,
        baseline_shelter_id="s1",
        baseline_route_id="r",
        baseline_route_edges=("a", "b"),
        origin_node=1,
        shelters=shelters,
        edge_rows=EDGES,
        decisions=decisions or {},
        triggering_road_segment="b",
    )


def test_concern_preserves_baseline():
    d = evaluate_accessibility(
        edge_id="b", timestamp="t", rainfall_3h_mm=14, rainfall_6h_mm=28, context=CTX
    )
    r = plan([ShelterOption("s1", 4, 10, "test")], {"b": d})
    assert r.decision_status == "baseline_preserved" and r.evidence["baseline_concern_edges"] == [
        "b"
    ]


def test_closed_excluded_and_same_shelter_rerouted():
    usable, bad, _ = route_status(("a", "b"), {"b": closed()})
    assert not usable and bad == ["b"]
    assert shortest_accessible_path(EDGES, {"b": closed()}, 1, 4).edge_ids == ("c", "d")
    assert (
        plan([ShelterOption("s1", 4, 10, "test")], {"b": closed()}).decision_status
        == "rerouted_same_shelter"
    )


def test_reassignment_capacity_tie_and_failure():
    d = {"b": closed()}
    r = plan(
        [
            ShelterOption("s1", 4, 2, "test"),
            ShelterOption("s2", 5, 10, "test"),
            ShelterOption("s0", 5, 10, "test"),
        ],
        d,
    )
    assert r.decision_status == "reassigned_alternative_shelter" and r.selected_shelter_id == "s0"
    assert (
        plan(
            [ShelterOption("s1", 4, 2, "test"), ShelterOption("s2", 5, 2, "test")], d
        ).decision_status
        == "no_feasible_plan"
    )
