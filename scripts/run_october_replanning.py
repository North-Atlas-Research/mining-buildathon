"""Run the real Passage Fort Drive WS25-011 replay from frozen outputs."""

from __future__ import annotations

import ast
import csv
import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd

from mining_sprint.accessibility_state import AccessibilityDecision
from mining_sprint.replanning import ShelterOption, replan_assignment

ROOT = Path("/workspace/data")
OUT = ROOT / "Outputs/ws25-011"
EDGE = "a1e99eb85ea1eb458f99a8130c2f3e3d5c121762cea8d70b960c31a8a0f5c960"
ROUTE = "route_98b39e4664a89ca29ad8ffb101c238fde326e93a9d888ab21c4072129a15c022"


def decision(row):
    return AccessibilityDecision(
        row["edge_id"],
        row["timestamp"],
        row["state"],
        row["environmental_concern"] == "True",
        row["observation_status"],
        float(row["rainfall_3h_mm"]),
        float(row["rainfall_6h_mm"]),
        row["context_label"],
        row["context_description"],
        row["context_susceptible"] == "True",
        tuple(ast.literal_eval(row["reason_codes"])),
        tuple(ast.literal_eval(row["provenance"])),
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((ROOT / "Outputs/ws25-010/accessibility_state_replay.csv").open()))
    cases = {r["scenario_case"]: decision(r) for r in rows}
    assert (
        cases["environmental_scenario"].state == "open_with_concern"
        and cases["operator_closed_scenario"].state == "closed"
    )
    routes = gpd.read_file(
        ROOT / "Processed/evacuation/portmore_route_reference_and_baseline_2020.gpkg",
        layer="network_baseline_routes",
    )
    base = routes.loc[routes.route_id == ROUTE].iloc[0]
    edges = ast.literal_eval(base.edge_ids_json)
    assert EDGE in edges
    comm = gpd.read_file(
        ROOT / "Processed/communities/portmore_community_zones_2020.gpkg",
        layer="portmore_community_zones_2020",
    )
    c = comm.loc[comm.community_id == base.origin_id].iloc[0]
    demand = math.ceil(float(c.resident_population_estimate) * 0.001)
    cn = pd.read_csv(ROOT / "Outputs/ws25-008/community_graph_connectors.csv").set_index(
        "community_id"
    )
    sn = pd.read_csv(ROOT / "Outputs/ws25-008/shelter_graph_connectors.csv")
    shelters = [
        ShelterOption(x.shelter_id, int(x.graph_node_id), 20, "scenario_nominal_capacity")
        for x in sn.itertuples()
    ]
    graph_frame = gpd.read_file(
        ROOT / "Processed/roads/portmore_road_graph_2020.gpkg", layer="portmore_road_edges_2020"
    )
    candidate = graph_frame.loc[graph_frame.edge_id == EDGE]
    if len(candidate) != 1 or int(candidate.iloc[0].osm_way_id) != 630666205:
        raise RuntimeError(
            "Passage Fort Drive candidate does not match frozen graph OSM way 630666205"
        )
    graph = graph_frame[["from_node", "to_node", "edge_id", "length_m"]].to_dict("records")
    kwargs = {
        "replay_timestamp": cases["operator_closed_scenario"].timestamp,
        "community_id": base.origin_id,
        "demand_people": demand,
        "baseline_shelter_id": base.destination_id,
        "baseline_route_id": base.route_id,
        "baseline_route_edges": edges,
        "origin_node": int(cn.loc[base.origin_id, "graph_node_id"]),
        "shelters": shelters,
        "edge_rows": graph,
        "triggering_road_segment": EDGE,
    }
    before = replan_assignment(**kwargs, decisions={EDGE: cases["environmental_scenario"]})
    after = replan_assignment(**kwargs, decisions={EDGE: cases["operator_closed_scenario"]})
    assert (
        before.decision_status == "baseline_preserved"
        and after.decision_status == "rerouted_same_shelter"
    )
    result = {
        "before": before.as_dict(),
        "after": after.as_dict(),
        "scenario": {
            "evacuation_fraction": 0.001,
            "nominal_capacity_people": 20,
            "capacity_is_not_observed_event_day_capacity": True,
            "closure_is_synthetic_not_historical_claim": True,
        },
    }
    (OUT / "passage_fort_replanning_result.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "validation.json").write_text(
        json.dumps(
            {
                "community_id": base.origin_id,
                "baseline_shelter_id": base.destination_id,
                "baseline_route_id": base.route_id,
                "baseline_distance_m": base.network_distance_m,
                "after_distance_m": after.selected_route.distance_m,
                "outcome": after.decision_status,
                "candidate_osm_way_id": int(candidate.iloc[0].osm_way_id),
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
