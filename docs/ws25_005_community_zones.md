# WS25-005 canonical Portmore community zones

## Scope and population firewall

This stage constructs community-zone geometry only. It does not acquire or
aggregate WorldPop, estimate evacuation or shelter demand, apply evacuation or
compliance percentages, or allocate shelters. Population remains a separate
unimplemented baseline-evidence stage.

The output contains 14 `mvp_operational_planning_zone` records. They are an MVP
operational planning construction, not statutory Portmore boundaries and not a
demonstrated reproduction of current official municipal community boundaries.

## Source selection

The primary layer is
`JM_GEOG2_ADM2_2012_uscb_202302`, documented in the local USCB workbook as
STATIN-reported 2012 community geography repackaged by USCB. It was selected
over GEOG1 because GEOG1 supplies a single Portmore special-area polygon, while
GEOG2 supplies recognizable community identities at the required granularity.

The source archive is `Raw/jamaica.gdb.zip`, SHA-256
`3b238b5618247f5dd98d2daaecc5442026f233779e3e823659bce6a35350603f`.
Lineage links the STATIN origin, USCB repackaging, local archive, and derived
planning zones. Local evidence does not establish permissive redistribution
rights, so status remains `unresolved_no_rights_claimed`.

## Deterministic inclusion and construction

Every positive-area source intersection is measured in EPSG:3448. The approved
Portmore-specific rule is:

`intersection_area_m2 / source_full_area_m2 >= 0.01`

This is not a generally valid community-selection threshold. It is justified
here by a clear source-specific separation: included units overlap by at least
28.1969% of their source area, while excluded traces overlap by no more than
0.0384%.

The 14 included source IDs are used one-to-one. Communities are neither
aggregated nor subdivided. Canonical geometry is exactly the source geometry
intersected with the frozen operational boundary in EPSG:3448. No buffer,
snapping, gap filling, hand drawing, dissolve, or silent repair is performed.

Four positive-area trace intersections remain outside the canonical layer and
are retained in `portmore_trace_intersections.csv`: Riverton Meadows, Bushy
Park, Caymana's, and Old Harbour Road.

## Identity and naming

The frozen UUID namespace is `0d710476-d218-52c0-aeb1-c3bcd144f704`, derived
as UUIDv5 of the project URL seed
`https://github.com/North-Atlas-Research/mining-sprint/ws25-005/community-zones`
under `NAMESPACE_URL`.

Each canonical identifier is `community_<uuid>` using this exact UUIDv5 seed:

`ws25-005|JM_GEOG2_ADM2_2012_uscb_202302|<GEO_MATCH>|direct_source_clipped_v1`

The ID does not depend on display name, normalized name, geometry, area,
population, or row order. `community_name_source` and
`source_geography_name` preserve `AREA_NAME` exactly. `community_name` is a
human-facing title form, and `community_name_normalized` is a deterministic
lowercase ASCII search key. No aliases are invented. `aggregation_members`
contains a deterministic JSON array with the single source `GEO_MATCH`.

## Boundary, gap, and review semantics

The canonical operational boundary remains the sole inclusion polygon. The
existing 750 m artifact remains a two-sided band around the boundary line used
only for review. It is not an inclusion polygon.

Nine original source units cross the operational boundary and are explicitly
marked as clipped. All 14 resulting zones intersect the edge-review band. No
canonical pair has positive-area overlap.

The canonical union leaves 367,582.67 m², or 0.201885% of the operational
boundary, uncovered. It is emitted as an unassigned diagnostic; no community or
unknown-zone record is fabricated. Excluded trace intersections explain
5,276.07 m², or 1.43534%, of that gap. Review entries cover crossings, edge
proximity, trace intersections, gap adjacency, large Hellshire/Cromarty zones,
and unresolved source licensing.

## Temporal semantics

`source_geometry_year` and `valid_time` are 2012. The year 2020 in the
canonical filename means the layer's role in the frozen Portmore 2020 regional
baseline. It does not assert that the source communities were surveyed or
created in 2020. Positional accuracy is not guaranteed by USCB, and the source
geometry may not represent later development.

## Artifacts

Generated outside Git:

- `Processed/communities/portmore_community_zones_2020.gpkg`, layer
  `portmore_community_zones_2020`, EPSG:3448;
- `Interim/communities/portmore_source_unit_crosswalk.csv`;
- `Interim/communities/portmore_community_identity_crosswalk.csv`;
- `Interim/communities/portmore_trace_intersections.csv`;
- `Outputs/ws25-005/validation.json`;
- `Outputs/ws25-005/lineage.json`;
- `Outputs/ws25-005/portmore_community_zones_preview_epsg4326.geojson`;
- `Outputs/ws25-005/operational_boundary_gap.geojson`;
- `Outputs/ws25-005/review_queue.csv`.

## Approved 2020 projected local-demographic population baseline

WS25-005 attaches one residential-population baseline to the unchanged 14-zone
canonical GeoPackage. It remains separate from evacuation demand, shelter
demand, compliance assumptions, and allocation.

WorldPop was evaluated because it nominally represented 2020. Both constrained
and unconstrained products were technically validated, but their operational
boundary totals (about 108,219.60 and 114,233.65 respectively) materially
under-allocated Portmore against stronger local demographic evidence. They are
retained as contextual/rejected evidence in their existing Raw and output
artifacts, not as canonical population authority. Where their diagnostics are
visible, `population_support_area_percent` and
`population_modeled_unsettled_area_percent` retain their WorldPop-specific
semantics.

The canonical value is a **projected 2020 Portmore population baseline**, not
an observed 2020 census count, event-day population, evacuation population, or
shelter demand. Its deterministic lineage is:

`STATIN 2011 Portmore TOTAL_POP (182153) -> Saint Catherine 2011--2019 parish
proxy extended one year -> normalized STATIN/USCB 2012 POV_ESTP community
weights -> frozen 14 planning zones`.

The exact projection is
`182153 * ((520502 / 516218) ** (9 / 8))`. `POV_ESTP` is retained as the
July 1, 2012 total-population-estimate distribution evidence and is normalized
across the 14 included communities (sum 171,546). The source `TOTAL POPULATION`
label does not explicitly say resident population. Saint Catherine growth is a
parish-level proxy because no later Portmore-specific local total was found;
community values are not observed 2020 counts. These temporal and spatial
uncertainties are explicitly `moderate` and require review.

The 0.201885% operational-boundary geometry gap remains an unassigned source
boundary artifact. No fifteenth zone or arbitrary population has been created;
the selected total is represented through the 14 recognized planning zones.

Generated outside Git:

- `Processed/communities/portmore_community_zones_2020.gpkg`, layer
  `portmore_community_zones_2020`, EPSG:3448, with canonical projected fields;
- `Interim/population/portmore_local_2020_population_baseline.csv`;
- `Outputs/ws25-005/validation.json`, `lineage.json`, `review_queue.csv`, and
  `community_population_preview_epsg4326.geojson`.
