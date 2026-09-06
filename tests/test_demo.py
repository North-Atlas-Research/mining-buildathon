import pytest

from mining_sprint.demo import load_replay, render


def replay():
    return {
        "previous_accessibility": {
            "state": "open_with_concern",
            "rainfall_3h_mm": 13.89,
            "rainfall_6h_mm": 28.76,
        },
        "new_accessibility": {"state": "closed"},
        "observation": {"status": "confirmed_closed"},
        "plan": {
            "community_id": "community-passage-fort",
            "selected_shelter_id": "shelter-portsmouth",
            "triggering_road_segment": "edge-passage-fort-drive",
            "decision_status": "rerouted_same_shelter",
            "selected_route": {"distance_m": 6690.54},
            "capacity_required": 11,
            "capacity_available": 20,
            "capacity_remaining": 9,
        },
        "human_review_required": True,
        "provenance": ["test"],
        "presentation": {
            "community": "Passage Fort",
            "shelter": "Portsmouth Primary School",
            "road": "Passage Fort Drive",
            "way": 630666205,
            "baseline_m": 661.70,
        },
        "explanation": "deterministic output",
    }


def test_render_uses_structured_values_and_boundaries():
    page = render(replay())
    for value in (
        "open_with_concern",
        "confirmed_closed",
        "rerouted_same_shelter",
        "6,690.54 m",
        "661.70 m",
        "11 / 20",
        "9 spaces remaining",
        "HUMAN REVIEW REQUIRED",
        "Synthetic replay input",
        "+6.03 km",
        "10.1× longer",
        "Passage Fort Drive",
        "Portsmouth Primary School",
        "OSM way 630666205",
    ):
        assert value in page
    assert "not a historical observation" in page and "no operational action" in page
    assert "Scenario-only capacity" in page


def test_missing_replay_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_replay(tmp_path)
