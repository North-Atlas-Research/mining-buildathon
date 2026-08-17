"""Read-only HTML presentation of the frozen WS25-012 coordination replay."""

from __future__ import annotations

import html
import json
from pathlib import Path


def load_replay(root: Path) -> dict:
    path = root / "Outputs/ws25-012/passage_fort_coordination.json"
    if not path.is_file():
        raise FileNotFoundError(f"Required coordination replay unavailable: {path}")
    replay = json.loads(path.read_text())
    required = ("previous_accessibility", "new_accessibility", "plan", "human_review_required")
    if any(key not in replay for key in required):
        raise ValueError("Coordination replay is missing required fields")
    validation = root / "Outputs/ws25-011/validation.json"
    if not validation.is_file():
        raise FileNotFoundError(f"Required replanning validation unavailable: {validation}")
    replay["baseline_distance_m"] = json.loads(validation.read_text())["baseline_distance_m"]
    return replay


def render(replay: dict) -> str:
    plan, before, after = (
        replay["plan"],
        replay["previous_accessibility"],
        replay["new_accessibility"],
    )

    def distance(value):
        return f"{float(value) / 1000:.2f} km ({float(value):,.2f} m)"

    return f"""<!doctype html><title>Portmore October Replay</title>
<h1>October Passage Fort replay</h1><p>Presentation only: deterministic project outputs; no operational action is executed.</p>
<section><h2>Historical/measured context</h2><p>Historical rainfall/context raised accessibility concern: {before["rainfall_3h_mm"]:.2f} mm / 3h; {before["rainfall_6h_mm"]:.2f} mm / 6h.</p><b>{before["state"]}</b><p>The road remains considered traversable; closure has not been established.</p></section>
<section><h2>Active-plan relevance</h2><p>Passage Fort Drive, OSM way 630666205, participates in the active Passage Fort baseline route.</p><p>Baseline shelter: Portsmouth Primary School. Baseline distance: {distance(replay["baseline_distance_m"])}.</p></section>
<section><h2>Structured operator replay input</h2><b>{html.escape(replay["observation"]["status"])}</b><p>Synthetic replay/operator input, not a historical observation.</p><button disabled>Approve</button> <button disabled>Reject</button> <button disabled>Request information</button></section>
<section><h2>Deterministic update</h2><b>{after["state"]}</b><p>Returned by WS25-010. WS25-011 returned {html.escape(plan["decision_status"])}.</p><p>Selected shelter: Portsmouth Primary School. Rerouted distance: {distance(plan["selected_route"]["distance_m"])}.</p><p>Scenario-only: demand {plan["capacity_required"]}; nominal capacity {plan["capacity_available"]}; remaining {plan["capacity_remaining"]}.</p></section>
<section><h2>Human review</h2><b>human_review_required</b><p>{html.escape(replay["explanation"])}</p><small>Route geometry unavailable; canonical textual/metric result shown.</small></section>"""
