"""Build the small, explicitly scenario-labelled WS25-010 October replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import xarray as xr
from pyproj import Transformer

from mining_sprint.accessibility_state import (
    ScenarioContext,
    evaluate_accessibility,
    rainfall_context_for_point,
    routing_semantics,
    validate_edge_id,
)

ROOT = Path("/workspace/data")
GRAPH = ROOT / "Processed/roads/portmore_road_graph_2020.gpkg"
ROUTES = ROOT / "Processed/evacuation/portmore_route_reference_and_baseline_2020.gpkg"
RAINFALL = ROOT / "Processed/rainfall/portmore_october_2020_imerg_v07b.nc"
OUTPUT = ROOT / "Outputs/ws25-010"

# A real directed edge used by WS25-008 route_2ae27...; scenario status below
# remains a test/replay assumption, not a claim about the October event.
CANDIDATE_EDGE_ID = "a1e99eb85ea1eb458f99a8130c2f3e3d5c121762cea8d70b960c31a8a0f5c960"
CANDIDATE_ROUTE_ID = "route_2ae27a4e32ad674580c132eedb98f11ce088440a57cf87c487dc48305c5901f9"
REPLAY_TIMESTAMP = "2020-10-05T17:00:00"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    edges = gpd.read_file(GRAPH, layer="portmore_road_edges_2020")
    candidate = edges.loc[edges.edge_id == CANDIDATE_EDGE_ID]
    if len(candidate) != 1:
        raise RuntimeError("WS25-010 candidate edge is absent or ambiguous in frozen graph")
    validate_edge_id(CANDIDATE_EDGE_ID, set(edges.edge_id))
    routes = gpd.read_file(ROUTES, layer="network_baseline_routes")
    candidate_route = routes.loc[routes.route_id == CANDIDATE_ROUTE_ID]
    if len(candidate_route) != 1 or CANDIDATE_EDGE_ID not in json.loads(candidate_route.iloc[0].edge_ids_json):
        raise RuntimeError("WS25-010 candidate edge is not present on its declared baseline route")
    geometry = candidate.iloc[0].geometry
    longitude, latitude = Transformer.from_crs(edges.crs, "EPSG:4326", always_xy=True).transform(
        geometry.centroid.x, geometry.centroid.y
    )

    with xr.open_dataset(RAINFALL) as dataset:
        rainfall = rainfall_context_for_point(dataset, REPLAY_TIMESTAMP, longitude, latitude)
    context = ScenarioContext(
        label="scenario_assumption",
        description=(
            "WS25-010 replay-only susceptibility/context flag for a real Passage Fort Drive "
            "edge; it is not an observed flood or susceptibility product."
        ),
        susceptible=True,
    )
    concern = evaluate_accessibility(
        edge_id=CANDIDATE_EDGE_ID,
        timestamp=REPLAY_TIMESTAMP,
        rainfall_3h_mm=rainfall["3h"]["value_mm"],
        rainfall_6h_mm=rainfall["6h"]["value_mm"],
        context=context,
    )
    closure = evaluate_accessibility(
        edge_id=CANDIDATE_EDGE_ID,
        timestamp=REPLAY_TIMESTAMP,
        rainfall_3h_mm=rainfall["3h"]["value_mm"],
        rainfall_6h_mm=rainfall["6h"]["value_mm"],
        context=context,
        observation_status="confirmed_closed",
    )
    rows = []
    for label, decision in (("environmental_scenario", concern), ("operator_closed_scenario", closure)):
        row = decision.as_dict()
        row.update(
            scenario_case=label,
            candidate_highway=candidate.iloc[0].highway,
            candidate_name=candidate.iloc[0]["name"],
            baseline_route_id=CANDIDATE_ROUTE_ID,
            routing_semantics=json.dumps(routing_semantics(decision.state), sort_keys=True),
            routing_consequence=(
                "baseline_route_remains_usable_with_review"
                if routing_semantics(decision.state)["usable"]
                else "baseline_route_contains_unusable_edge_replanning_required"
            ),
            rainfall_3h_lookup=json.dumps(rainfall["3h"], sort_keys=True),
            rainfall_6h_lookup=json.dumps(rainfall["6h"], sort_keys=True),
        )
        rows.append(row)
    replay_path = OUTPUT / "accessibility_state_replay.csv"
    pd.DataFrame(rows).to_csv(replay_path, index=False)
    validation = {
        "candidate_edge_id": CANDIDATE_EDGE_ID,
        "candidate_osm_way_id": int(candidate.iloc[0].osm_way_id),
        "candidate_highway": candidate.iloc[0].highway,
        "candidate_route_id": CANDIDATE_ROUTE_ID,
        "candidate_is_in_baseline_route": True,
        "replay_timestamp_utc": REPLAY_TIMESTAMP + "Z",
        "environmental_state": concern.state,
        "closed_observation_state": closure.state,
        "closure_requires_replanning": not routing_semantics(closure.state)["usable"],
        "scenario_is_not_observed_flooding": True,
        "source_graph_sha256": sha256(GRAPH),
        "source_routes_sha256": sha256(ROUTES),
        "source_rainfall_sha256": sha256(RAINFALL),
    }
    (OUTPUT / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    lineage = {
        "workstream": "WS25-010",
        "inputs": [str(GRAPH), str(ROUTES), str(RAINFALL)],
        "output": str(replay_path),
        "evidence_classes": ["frozen_rainfall_context", "scenario_assumption", "trusted_operator_observation"],
        "exclusions": ["no_flood_inference", "no_hydrological_model", "no_synthetic_graph_connections"],
    }
    (OUTPUT / "lineage.json").write_text(json.dumps(lineage, indent=2) + "\n")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
