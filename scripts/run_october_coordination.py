"""Run the structured WS25-012 Passage Fort coordination replay."""

from __future__ import annotations

import ast
import csv
import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd

from mining_sprint.accessibility_state import AccessibilityDecision
from mining_sprint.coordination import StructuredObservation, coordinate
from mining_sprint.replanning import ShelterOption

ROOT = Path("/workspace/data")
OUT = ROOT / "Outputs/ws25-012"
EDGE = "a1e99eb85ea1eb458f99a8130c2f3e3d5c121762cea8d70b960c31a8a0f5c960"
ROUTE = "route_98b39e4664a89ca29ad8ffb101c238fde326e93a9d888ab21c4072129a15c022"


def decision(r):
    return AccessibilityDecision(
        r["edge_id"],
        r["timestamp"],
        r["state"],
        r["environmental_concern"] == "True",
        r["observation_status"],
        float(r["rainfall_3h_mm"]),
        float(r["rainfall_6h_mm"]),
        r["context_label"],
        r["context_description"],
        r["context_susceptible"] == "True",
        tuple(ast.literal_eval(r["reason_codes"])),
        tuple(ast.literal_eval(r["provenance"])),
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {
        r["scenario_case"]: decision(r)
        for r in csv.DictReader((ROOT / "Outputs/ws25-010/accessibility_state_replay.csv").open())
    }
    current = cases["environmental_scenario"]
    assert current.state == "open_with_concern"
    routes = gpd.read_file(
        ROOT / "Processed/evacuation/portmore_route_reference_and_baseline_2020.gpkg",
        layer="network_baseline_routes",
    )
    base = routes.loc[routes.route_id == ROUTE].iloc[0]
    path = ast.literal_eval(base.edge_ids_json)
    assert EDGE in path
    comm = gpd.read_file(
        ROOT / "Processed/communities/portmore_community_zones_2020.gpkg",
        layer="portmore_community_zones_2020",
    )
    pop = comm.loc[comm.community_id == base.origin_id].iloc[0].resident_population_estimate
    cn = pd.read_csv(ROOT / "Outputs/ws25-008/community_graph_connectors.csv").set_index(
        "community_id"
    )
    sn = pd.read_csv(ROOT / "Outputs/ws25-008/shelter_graph_connectors.csv")
    graph = gpd.read_file(
        ROOT / "Processed/roads/portmore_road_graph_2020.gpkg", layer="portmore_road_edges_2020"
    )[["from_node", "to_node", "edge_id", "length_m"]].to_dict("records")
    kw = {
        "replay_timestamp": current.timestamp,
        "community_id": base.origin_id,
        "demand_people": math.ceil(float(pop) * 0.001),
        "baseline_shelter_id": base.destination_id,
        "baseline_route_id": base.route_id,
        "baseline_route_edges": path,
        "origin_node": int(cn.loc[base.origin_id, "graph_node_id"]),
        "shelters": [
            ShelterOption(x.shelter_id, int(x.graph_node_id), 20, "scenario_nominal_capacity")
            for x in sn.itertuples()
        ],
        "edge_rows": graph,
        "triggering_road_segment": EDGE,
    }
    out = coordinate(
        current,
        StructuredObservation(
            EDGE, "confirmed_closed", "trusted_synthetic_operator", "trusted", "synthetic_replay"
        ),
        kw,
    )
    assert (
        out["plan"]["decision_status"] == "rerouted_same_shelter" and out["human_review_required"]
    )
    (OUT / "passage_fort_coordination.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
