"""Deterministic, evidence-labelled road accessibility states for WS25-010.

This module deliberately does not infer flooding or closures from rainfall.  It
combines frozen rainfall context with an explicitly labelled scenario/context
flag, then lets trusted road observations determine operational restrictions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from mining_sprint.rainfall import rainfall_lookup

AccessibilityState = Literal["open", "open_with_concern", "uncertain", "restricted", "closed"]
ObservationStatus = Literal["unknown", "confirmed_open", "restricted", "confirmed_closed"]

DEFAULT_STATE: AccessibilityState = "open"
CONCERN_3H_MM = 10.0
CONCERN_6H_MM = 20.0


@dataclass(frozen=True)
class ScenarioContext:
    """Non-authoritative contextual evidence for a reproducible replay."""

    label: str = "scenario_assumption"
    description: str = "No scenario context supplied"
    susceptible: bool = False


NO_SCENARIO_CONTEXT = ScenarioContext()


@dataclass(frozen=True)
class AccessibilityDecision:
    """A fully reconstructable state decision for one graph edge and instant."""

    edge_id: str
    timestamp: str
    state: AccessibilityState
    environmental_concern: bool
    observation_status: ObservationStatus
    rainfall_3h_mm: float | None
    rainfall_6h_mm: float | None
    context_label: str
    context_description: str
    context_susceptible: bool
    reason_codes: tuple[str, ...]
    provenance: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return JSON/CSV-friendly evidence, retaining lists rather than hiding them."""
        result = asdict(self)
        result["reason_codes"] = list(self.reason_codes)
        result["provenance"] = list(self.provenance)
        return result


def validate_edge_id(edge_id: str, graph_edge_ids: set[str]) -> None:
    """Reject scenarios which do not reference the frozen historical graph."""
    if edge_id not in graph_edge_ids:
        raise ValueError(f"Unknown historical graph edge ID: {edge_id}")


def routing_semantics(state: AccessibilityState) -> dict[str, object]:
    """Return deterministic downstream routing treatment without changing the planner."""
    policies = {
        "open": {"usable": True, "cost_multiplier": 1.0, "review_required": False},
        "open_with_concern": {"usable": True, "cost_multiplier": 1.0, "review_required": True},
        "uncertain": {"usable": True, "cost_multiplier": 1.5, "review_required": True},
        "restricted": {"usable": True, "cost_multiplier": 2.0, "review_required": True},
        "closed": {"usable": False, "cost_multiplier": None, "review_required": True},
    }
    try:
        return {"state": state, **policies[state]}
    except KeyError as error:
        raise ValueError(f"Unsupported accessibility state: {state}") from error


def _environmental_concern(
    rainfall_3h_mm: float | None, rainfall_6h_mm: float | None, context: ScenarioContext
) -> tuple[bool, list[str]]:
    rainfall_elevated = (
        rainfall_3h_mm is not None
        and rainfall_3h_mm >= CONCERN_3H_MM
        or rainfall_6h_mm is not None
        and rainfall_6h_mm >= CONCERN_6H_MM
    )
    reasons: list[str] = []
    if rainfall_elevated:
        reasons.append("rainfall_demo_concern_threshold_met")
    if context.susceptible:
        reasons.append("scenario_context_susceptible")
    return rainfall_elevated and context.susceptible, reasons


def evaluate_accessibility(
    *,
    edge_id: str,
    timestamp: datetime | str,
    rainfall_3h_mm: float | None,
    rainfall_6h_mm: float | None,
    context: ScenarioContext = NO_SCENARIO_CONTEXT,
    observation_status: ObservationStatus = "unknown",
) -> AccessibilityDecision:
    """Evaluate one edge with explicit precedence and no flood/closure inference.

    The 3h/6h thresholds are demo concern thresholds, not calibrated flood
    thresholds.  Environmental evidence only yields ``open_with_concern``.
    """
    timestamp_text = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp)
    concern, reasons = _environmental_concern(rainfall_3h_mm, rainfall_6h_mm, context)
    provenance = ["frozen_ws25_009_imerg_context", context.label]
    state: AccessibilityState = "open_with_concern" if concern else DEFAULT_STATE
    if concern:
        reasons.append("environmental_inference_open_with_concern")
    else:
        reasons.append("default_open_no_confirmed_operational_constraint")

    observation_rules: dict[ObservationStatus, tuple[AccessibilityState, str]] = {
        "confirmed_open": ("open", "trusted_observation_confirmed_open_override"),
        "restricted": ("restricted", "trusted_observation_restricted_override"),
        "confirmed_closed": ("closed", "trusted_observation_confirmed_closed_override"),
        "unknown": (state, "no_trusted_observation"),
    }
    if observation_status not in observation_rules:
        raise ValueError(f"Unsupported observation status: {observation_status}")
    state, observation_reason = observation_rules[observation_status]
    reasons.append(observation_reason)
    if observation_status != "unknown":
        provenance.append("trusted_operator_observation")

    return AccessibilityDecision(
        edge_id=edge_id,
        timestamp=timestamp_text,
        state=state,
        environmental_concern=concern,
        observation_status=observation_status,
        rainfall_3h_mm=rainfall_3h_mm,
        rainfall_6h_mm=rainfall_6h_mm,
        context_label=context.label,
        context_description=context.description,
        context_susceptible=context.susceptible,
        reason_codes=tuple(reasons),
        provenance=tuple(provenance),
    )


def rainfall_context_for_point(dataset, timestamp, longitude: float, latitude: float) -> dict[str, object]:
    """Read the two approved frozen-IMERG windows using the WS25-009 lookup."""
    return {
        "3h": rainfall_lookup(dataset, timestamp, longitude, latitude, "3h"),
        "6h": rainfall_lookup(dataset, timestamp, longitude, latitude, "6h"),
    }
