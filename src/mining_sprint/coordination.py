"""Deterministic human-in-the-loop coordination over WS25-010 and WS25-011."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from mining_sprint.accessibility_state import (
    AccessibilityDecision,
    ScenarioContext,
    evaluate_accessibility,
)
from mining_sprint.replanning import ReplanningResult, replan_assignment

OperatorStatus = Literal["confirmed_open", "restricted", "confirmed_closed"]


@dataclass(frozen=True)
class StructuredObservation:
    edge_id: str
    status: OperatorStatus
    source: str
    trust: Literal["trusted"]
    scenario_label: str


def status_request(current: AccessibilityDecision, active_route_id: str) -> dict[str, object]:
    """Request one constrained operator status; no free-form prose is interpreted."""
    return {
        "edge_id": current.edge_id,
        "active_route_id": active_route_id,
        "previous_state": current.state,
        "required_fields": ["status", "source", "trust", "scenario_label"],
        "allowed_statuses": ["confirmed_open", "restricted", "confirmed_closed"],
        "human_review_required": True,
    }


def coordinate(
    current: AccessibilityDecision, observation: StructuredObservation, replan_kwargs: dict
) -> dict[str, object]:
    """Apply a trusted structured observation then delegate planning unchanged."""
    if observation.trust != "trusted" or observation.edge_id != current.edge_id:
        raise ValueError("Observation must be trusted and reference the active accessibility edge")
    updated = evaluate_accessibility(
        edge_id=current.edge_id,
        timestamp=current.timestamp,
        rainfall_3h_mm=current.rainfall_3h_mm,
        rainfall_6h_mm=current.rainfall_6h_mm,
        context=ScenarioContext(
            current.context_label, current.context_description, current.context_susceptible
        ),
        observation_status=observation.status,
    )
    result: ReplanningResult = replan_assignment(
        **replan_kwargs, decisions={updated.edge_id: updated}
    )
    return {
        "request": status_request(current, replan_kwargs["baseline_route_id"]),
        "observation": asdict(observation),
        "previous_accessibility": current.as_dict(),
        "new_accessibility": updated.as_dict(),
        "plan": result.as_dict(),
        "reason_codes": ["structured_trusted_observation_applied", *result.reason_codes],
        "provenance": [
            "ws25_010_accessibility_state",
            "ws25_011_deterministic_replanning",
            observation.scenario_label,
        ],
        "human_review_required": True,
        "explanation": (
            f"Structured trusted status produced {updated.state}; WS25-011 returned "
            f"{result.decision_status} for shelter {result.selected_shelter_id}. "
            "Human review is required; no action is executed automatically."
        ),
    }
