from datetime import UTC, datetime

import pytest

from mining_sprint.accessibility_state import (
    ScenarioContext,
    evaluate_accessibility,
    rainfall_context_for_point,
    routing_semantics,
    validate_edge_id,
)

EDGE = "real-frozen-edge"
CONTEXT = ScenarioContext("scenario_assumption", "replay-only context", True)


def decide(**kwargs):
    return evaluate_accessibility(
        edge_id=EDGE,
        timestamp=datetime(2020, 10, 5, 17, tzinfo=UTC),
        rainfall_3h_mm=14.0,
        rainfall_6h_mm=28.0,
        context=CONTEXT,
        **kwargs,
    )


def test_environmental_concern_is_deterministic_and_not_a_closure():
    assert decide() == decide()
    result = decide()
    assert result.state == "open_with_concern"
    assert result.environmental_concern is True
    assert "flood" not in " ".join(result.reason_codes).lower()


def test_rainfall_or_context_alone_never_closes_a_road():
    rainfall_only = evaluate_accessibility(
        edge_id=EDGE, timestamp="t", rainfall_3h_mm=14, rainfall_6h_mm=28
    )
    context_only = evaluate_accessibility(
        edge_id=EDGE, timestamp="t", rainfall_3h_mm=0, rainfall_6h_mm=0, context=CONTEXT
    )
    assert rainfall_only.state == context_only.state == "open"
    assert not rainfall_only.environmental_concern


def test_trusted_observations_override_but_retain_environmental_evidence():
    opened = decide(observation_status="confirmed_open")
    closed = decide(observation_status="confirmed_closed")
    assert opened.state == "open"
    assert closed.state == "closed"
    assert opened.environmental_concern and closed.environmental_concern
    assert opened.context_label == "scenario_assumption"
    assert "trusted_operator_observation" in closed.provenance


def test_restricted_has_explicit_routing_treatment():
    result = decide(observation_status="restricted")
    assert result.state == "restricted"
    assert routing_semantics(result.state) == {
        "state": "restricted",
        "usable": True,
        "cost_multiplier": 2.0,
        "review_required": True,
    }
    assert routing_semantics("closed")["usable"] is False


def test_graph_edge_identifiers_are_validated():
    validate_edge_id(EDGE, {EDGE})
    with pytest.raises(ValueError, match="Unknown historical graph edge ID"):
        validate_edge_id(EDGE, set())


def test_rainfall_lookup_uses_the_approved_windows(monkeypatch):
    calls = []

    def lookup(dataset, timestamp, longitude, latitude, window):
        calls.append((timestamp, longitude, latitude, window))
        return {"window": window, "value_mm": 1.0}

    monkeypatch.setattr("mining_sprint.accessibility_state.rainfall_lookup", lookup)
    result = rainfall_context_for_point("dataset", "time", -76.9, 18.0)
    assert list(result) == ["3h", "6h"]
    assert calls == [("time", -76.9, 18.0, "3h"), ("time", -76.9, 18.0, "6h")]
