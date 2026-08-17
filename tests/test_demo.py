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
            "decision_status": "rerouted_same_shelter",
            "selected_route": {"distance_m": 6690.54},
            "capacity_required": 11,
            "capacity_available": 20,
            "capacity_remaining": 9,
        },
        "human_review_required": True,
        "baseline_distance_m": 661.70,
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
        "demand 11",
        "remaining 9",
        "human_review_required",
    ):
        assert value in page
    assert "not a historical observation" in page and "no operational action" in page


def test_missing_replay_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_replay(tmp_path)
