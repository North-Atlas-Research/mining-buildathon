from mining_sprint.accessibility_state import ScenarioContext, evaluate_accessibility
from mining_sprint.coordination import StructuredObservation, coordinate, status_request
from mining_sprint.replanning import ShelterOption

EDGES = [
    {"from_node": 1, "to_node": 2, "edge_id": "a", "length_m": 1},
    {"from_node": 2, "to_node": 3, "edge_id": "b", "length_m": 1},
    {"from_node": 1, "to_node": 3, "edge_id": "c", "length_m": 3},
]


def test_structured_closure_delegates_to_state_and_replanning():
    cur = evaluate_accessibility(
        edge_id="b",
        timestamp="t",
        rainfall_3h_mm=14,
        rainfall_6h_mm=28,
        context=ScenarioContext("scenario_assumption", "test", True),
    )
    kw = {
        "replay_timestamp": "t",
        "community_id": "c",
        "demand_people": 1,
        "baseline_shelter_id": "s",
        "baseline_route_id": "r",
        "baseline_route_edges": ("a", "b"),
        "origin_node": 1,
        "shelters": [ShelterOption("s", 3, 2, "scenario")],
        "edge_rows": EDGES,
        "triggering_road_segment": "b",
    }
    out = coordinate(
        cur,
        StructuredObservation(
            "b", "confirmed_closed", "test operator", "trusted", "synthetic_replay"
        ),
        kw,
    )
    assert status_request(cur, "r")["human_review_required"]
    assert out["new_accessibility"]["state"] == "closed"
    assert out["plan"]["decision_status"] == "rerouted_same_shelter"
    assert out["human_review_required"]
    assert "rerouted_same_shelter" in out["explanation"]


def test_untrusted_or_wrong_edge_is_rejected():
    cur = evaluate_accessibility(edge_id="b", timestamp="t", rainfall_3h_mm=0, rainfall_6h_mm=0)
    kw = {
        "replay_timestamp": "t",
        "community_id": "c",
        "demand_people": 1,
        "baseline_shelter_id": "s",
        "baseline_route_id": "r",
        "baseline_route_edges": ("a",),
        "origin_node": 1,
        "shelters": [ShelterOption("s", 2, 2, "x")],
        "edge_rows": EDGES,
        "triggering_road_segment": "b",
    }
    try:
        coordinate(cur, StructuredObservation("x", "confirmed_closed", "x", "trusted", "x"), kw)
    except ValueError:
        pass
    else:
        raise AssertionError("wrong edge accepted")
