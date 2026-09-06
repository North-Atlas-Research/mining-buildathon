"""Read-only HTML operations dashboard for the frozen WS25-012 replay."""

from __future__ import annotations

import html
import json
from pathlib import Path

import geopandas as gpd


def _file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Required input unavailable: {path}")
    return path


def _one(frame, key: str, value: str):
    result = frame.loc[frame[key] == value]
    if len(result) != 1:
        raise ValueError(f"Expected one {key}={value}, found {len(result)}")
    return result.iloc[0]


def load_replay(root: Path) -> dict:
    """Load structured facts and canonical display labels without making decisions."""
    replay = json.loads(_file(root, "Outputs/ws25-012/passage_fort_coordination.json").read_text())
    if any(
        key not in replay
        for key in ("previous_accessibility", "new_accessibility", "plan", "human_review_required")
    ):
        raise ValueError("Coordination replay is missing required fields")
    plan = replay["plan"]
    validation = json.loads(_file(root, "Outputs/ws25-011/validation.json").read_text())
    communities = gpd.read_file(
        _file(root, "Processed/communities/portmore_community_zones_2020.gpkg"),
        layer="portmore_community_zones_2020",
    )
    shelters = gpd.read_file(
        _file(root, "Processed/shelters/portmore_shelters_2019.gpkg"),
        layer="portmore_shelters_2019",
    )
    roads = gpd.read_file(
        _file(root, "Processed/roads/portmore_road_graph_2020.gpkg"),
        layer="portmore_road_edges_2020",
    )
    community = _one(communities, "community_id", plan["community_id"])
    shelter = _one(shelters, "shelter_id", plan["selected_shelter_id"])
    road = _one(roads, "edge_id", plan["triggering_road_segment"])
    replay["presentation"] = {
        "community": community.community_name,
        "shelter": shelter.display_name,
        "road": " ".join(str(road["name"]).replace("%", " ").split()),
        "way": int(road.osm_way_id),
        "baseline_m": validation["baseline_distance_m"],
    }
    return replay


def render(replay: dict) -> str:
    """Render existing facts only; this function never determines an outcome."""
    plan, before, after, label = (
        replay["plan"],
        replay["previous_accessibility"],
        replay["new_accessibility"],
        replay["presentation"],
    )
    safe = lambda value: html.escape(str(value))
    baseline_m = float(label["baseline_m"])
    reroute_m = float(plan["selected_route"]["distance_m"])
    additional_m = reroute_m - baseline_m
    multiplier = reroute_m / baseline_m

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Passage Fort Evacuation Coordination Replay</title><style>
:root{{--ink:#172534;--muted:#526579;--bg:#f4f7fa;--line:#dbe4ec;--teal:#146c73;--amber:#e7a432;--red:#c74747;--violet:#7359bb}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:32px}}h1{{margin:4px 0 8px;font-size:clamp(2rem,5vw,3rem)}}h2{{font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:30px}}.eyebrow,.tag{{color:var(--teal);font-size:.78rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}}.muted,small{{color:var(--muted)}}.flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;align-items:stretch}}.flow-card,.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 1px 2px #d7e0e833}}.flow-card{{position:relative}}.flow-card:not(:last-child)::after{{content:"→";position:absolute;right:-10px;top:42%;z-index:2;color:var(--teal);font-weight:800;font-size:1.4rem}}.flow-value{{display:block;font-size:1.08rem;font-weight:800;margin:8px 0}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}}.metric{{display:block;font-size:2rem;font-weight:800;line-height:1.05;margin:10px 0 4px}}.metric small{{display:block;font-size:.75rem;font-weight:500;margin-top:6px}}.concern{{border-top:6px solid var(--amber)}}.closed{{border-top:6px solid var(--red)}}.review{{border-top:6px solid var(--violet)}}.synthetic{{background:#fff1f1;color:#a13232;border-radius:999px;padding:4px 8px;font-size:.7rem;font-weight:800;letter-spacing:.06em}}.review .metric{{font-size:1.65rem;color:#573f9d}}details{{margin-top:22px}}@media(max-width:780px){{main{{padding:20px}}.flow,.grid{{grid-template-columns:1fr 1fr}}.flow-card:not(:last-child)::after{{display:none}}}}@media(max-width:500px){{.flow,.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<p class="eyebrow">Presentation-only operations dashboard · October 2020 replay</p><h1>Passage Fort Evacuation Coordination Replay</h1><p class="muted">{safe(label["road"])} · OSM way {label["way"]} · no operational action is executed.</p>
<h2>Evidence flow</h2><div class="flow"><section class="flow-card"><span class="tag">Historical / measured</span><span class="flow-value">{before["rainfall_3h_mm"]:.2f} / {before["rainfall_6h_mm"]:.2f} mm</span><small>3h / 6h rainfall context</small></section><section class="flow-card concern"><span class="tag">Environmental inference</span><span class="flow-value">{safe(before["state"])}</span><small>Traversable; concern does not establish closure.</small></section><section class="flow-card"><span class="synthetic">Synthetic replay input</span><span class="flow-value">{safe(replay["observation"]["status"])}</span><small>Trusted operator-supplied replay input; not a historical observation.</small></section><section class="flow-card closed"><span class="tag">Deterministic outputs</span><span class="flow-value">{safe(after["state"])}</span><small>{safe(plan["decision_status"])}</small></section></div>
<h2>Before / after plan</h2><div class="grid"><section class="card concern"><span class="tag">Before · route valid</span><span class="metric">{baseline_m / 1000:.2f} km<small>{baseline_m:,.2f} m baseline route</small></span><p><b>{safe(label["shelter"])}</b></p></section><section class="card closed"><span class="tag">After · same shelter</span><span class="metric">{reroute_m / 1000:.2f} km<small>{reroute_m:,.2f} m deterministic reroute</small></span><p>{safe(plan["decision_status"])}</p><small>+{additional_m / 1000:.2f} km · {multiplier:.1f}× longer</small></section><section class="card"><span class="tag">Scenario-only capacity</span><span class="metric">{plan["capacity_required"]} / {plan["capacity_available"]}<small>demand / nominal capacity</small></span><p><b>{plan["capacity_remaining"]} spaces remaining</b></p><small>Scenario assumptions/results, not observed demand or event-day capacity.</small></section><section class="card review"><span class="tag">Terminal state</span><span class="metric">HUMAN REVIEW REQUIRED</span><p>No action executed automatically.</p><small>Deterministic replay result awaits human review.</small></section></div>
<details><summary>Structured provenance and identifiers</summary><p>Community ID: {safe(plan["community_id"])}<br>Shelter: {safe(label["shelter"])} · ID: {safe(plan["selected_shelter_id"])}<br>Road edge ID: {safe(plan["triggering_road_segment"])}<br>Provenance: {safe(", ".join(replay["provenance"]))}</p></details><p class="muted"><small>Route geometry is unavailable in this replay artifact; canonical textual and metric results are shown.</small></p>
</main></body></html>"""
