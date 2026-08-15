# WS25-004 shelter canonicalization

## Scope

This stage produces a 20-record canonical shelter layer from the approved
field-preserving ODPEM transcription and identity/location evidence. It retains
the 18 Portmore-section rows and the two source-designated emergency shelters
outside Portmore. It performs no silent merge and creates no service-area
polygon.

The result is a historical source baseline, not evidence that a shelter was
open, usable, or available during any 2020 event. Spatial classifications use
the MVP operational boundary and are not legal municipal determinations.

## Identifier contract

`source_record_id` identifies an immutable printed ODPEM row.
`resolution_candidate_id` crosswalks that row to the identity-resolution stage.
The final `shelter_id` is `shelter_` followed by the 32 lowercase hexadecimal
characters of UUIDv5. The namespace is
`fd877461-830a-54ad-83a7-c0cbaeb7c004`; the seed is the exact immutable
`source_record_id` string (for example, `odpem2019-pm-001`). It does not include
display name, coordinates, capacity, priority, normalized areas, or any other
mutable field, and therefore remains stable across later corrections. All three identifiers are stored together. No records
are merged.

## Capacity and time

`capacity_raw` is preserved exactly. Only ASCII integer text is parsed into
`source_capacity`; `N/A` and blanks become null, never zero.
`source_capacity_unit` is `not_established`. `baseline_capacity` carries the
same historical parsed number with an explicit
`historical_source_value_with_unestablished_unit_not_verified_operational_capacity`
semantic label; it is not a claim of operational usability. The legacy explicit
alias `historical_listed_capacity` carries the same value.
`capacity_status` has these semantics:

- `stated`: clearly numeric source text was parsed;
- `missing`: source text was blank or `N/A`;
- `ambiguous`: source text was non-empty but not clearly numeric;
- `conflicting`: authoritative evidence supplies incompatible values requiring
  review.

The current records contain 17 stated and three missing values. No authoritative
source establishes that the printed capacity unit means persons, so
`capacity_unit` is `not_established`. Historical listed capacity is separate
from null `operational_usable_capacity` and its `unknown` status.

Temporal fields distinguish the ODPEM-listed/designated baseline, source year
2019, unknown event-specific status, unknown operational availability, system
recorded time, and reserved null human-override fields. Later evidence used for
identity/location does not overwrite the 2019 baseline.

## Areas served

`areas_served_raw` remains exact. No normalized community references or service
polygons are accepted at this stage. The normalized value is null, matching
method is `not_performed`, confidence is `unresolved`, and every record is sent
to review. Any future normalized reference must record its matching method,
confidence, and review decision.

## Geometry decisions

Thirteen medium-confidence present-day OSM candidates are accepted as canonical
working points because their named mapped feature is consistent with the ODPEM
identity/address and documented official corroboration. This is a documented
MVP evidence decision, not proof of 2019/2020 operation.

OSM way coordinates retain `mapped_facility_area_centroid` precision and are
explicitly computed way centroids—not building centroids or entrances. The
Waterford OSM node remains a `mapped_facility_point`, not an asserted entrance.
Competing candidates for Bridgeport High, Independence City Primary, and G.C.
Foster College remain in the evidence table; the named facility-area candidate
is selected and the alternative/reason remains reviewable.

Seven facilities remain explicit null geometries: Assembly of Righteousness,
Bethel Gospel Assembly, Clifton Basic School, Glad Tidings Church, HEART College
of Construction Services, Hellshire United Pentecostal Church, and Southborough
Primary School. Their boundary, edge-band, and context classifications are null
with status `unknown`, and location review remains required.

## Spatial classification

Accepted EPSG:3448 points are classified reproducibly using:

- `Processed/region/portmore_boundary.gpkg` as the operational inclusion
  polygon;
- the two-sided 750 m band around the boundary line for edge review only;
- the 2,000 m acquisition/context buffer.

G.C. Foster College and National Arena are outside the operational boundary and
context buffer, but remain canonical because the ODPEM source explicitly lists
them as emergency shelters outside Portmore. Their source-defined relevance is
stored separately from spatial inclusion.

## Outputs and attribution

Generated project-data artifacts are:

- `Processed/shelters/portmore_shelters_2019.gpkg`, layer
  `portmore_shelters_2019`, EPSG:3448;
- `Outputs/ws25-004/portmore_shelters_2019_preview_epsg4326.geojson`;
- `Outputs/ws25-004/lineage.json`;
- `Outputs/ws25-004/validation.json`;
- `Outputs/ws25-004/consolidated_review_queue.csv`.

The canonical layer and preview expose all 20 rows, including seven records with
null geometry. Relevant records carry ODbL 1.0 and
[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright)
attribution. No PDF, map tile, screenshot, or temporary HTTP response is bundled.
