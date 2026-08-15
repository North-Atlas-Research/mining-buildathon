# WS25-004 shelter identity and geolocation review

## Scope and identifier contract

This stage records unresolved identities and preliminary locations. It does not
merge records, normalize capacity, classify against the Portmore boundary,
select canonical geometry, or generate a GeoPackage.

All 20 rows and raw transcription fields remain unchanged. Identifiers have
three deliberately separate roles:

- `source_record_id` is an immutable ODPEM printed-record identifier derived
  only from the printed section and row order;
- `canonical_candidate_id` identifies an unresolved shelter-entity candidate
  during review and is independent of its display name;
- a final canonical shelter ID will be assigned only after identity decisions
  are accepted. No current candidate ID is a final shelter ID.

## Evidence hierarchy and confidence

Location and identity research uses this order:

1. ODPEM's 2019 source record;
2. official government and Portmore Municipal Council records;
3. official educational or facility records, including MOEY, ECC, HEART/NSTA,
   and the facility's own institutional site;
4. authoritative address or parcel evidence where available;
5. OpenStreetMap and its public Nominatim service as supplementary evidence;
6. general directories as supplementary evidence; commercial maps are for
   discovery only and are not accepted silently as authority.

Identity confidence and location confidence are independent dimensions:

- **High identity confidence:** an official record corroborates the source name
  and address/community, or multiple authoritative records establish the same
  facility identity.
- **Medium identity confidence:** the named entity is plausible and partly
  corroborated, but an address, naming, or intended-building question remains.
- **Low identity confidence:** only weak, ambiguous, or uncorroborated evidence
  connects the source row to a present-day entity.
- **High location confidence:** an authoritative coordinate, parcel, verified
  facility footprint, or identified entrance directly locates the accepted
  facility.
- **Medium location confidence:** a supplementary mapped facility feature is
  consistent with official identity/address evidence, but its representative
  point or footprint still requires review.
- **Low location confidence:** a plausible coordinate has only weak or
  conflicting support. Low-confidence evidence is not accepted as geometry.

Current counts are 16 high, two medium, and two low for identity. Thirteen
entities have medium-confidence coordinate candidates; none has high- or
low-confidence accepted coordinates. Seven remain geometry-null.

Official evidence includes Portmore municipal shelter records, the Ministry of
Education 2018/19 directory, the Early Childhood Commission, HEART/NSTA,
Southborough Primary School, and later official shelter lists used only for
identity corroboration. No possible duplicate was merged. Four identities
remain in manual review.

## OpenStreetMap and Nominatim compliance

OSM data is licensed under ODbL 1.0 and must be publicly attributed as
[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright).
Nominatim use follows the
[public usage policy](https://operations.osmfoundation.org/policies/nominatim/):
a one-time controlled small-batch pass was run on one machine and one thread,
with an identifying user agent, at least 1.05 seconds between request starts,
and cached results. No map tiles, screenshots, or layout reproductions are
stored.

The audit caches are reproducible external working artifacts, not Git inputs:

- `/workspace/data/Cache/ws25-004/nominatim_audit_20260815.json`, SHA-256
  `7b48e5c775d9566dd6d23096613d64a5a7de9810d6e21e31a5417c4aa1baf644`;
- `/workspace/data/Cache/ws25-004/nominatim_targeted_unresolved_20260815.json`,
  SHA-256 `56433d6e09e9dcc754d42468776c11dbf270a28e3769804fe3e8120d667113ee`.

Each OSM candidate preserves its exact query, retrieval timestamp, OSM type and
ID, element URL, returned display name and class/type, source latitude and
longitude, node-versus-computed-way-centroid representation, ODbL identifier,
and evidence observation date. This is factual response metadata for auditing;
it is not a copy of the map.

OSM evidence describes the present-day mapped facility location only. It does not prove 2019 or 2020 shelter operation, operational status, event
availability,
or capacity. Way coordinates are computed feature centroids, not claimed
building centroids; nodes are mapped facility points, not claimed entrances.

## Location review results

Sixteen preliminary OSM coordinate rows cover 13 entities. All require manual
review; no canonical coordinate has been selected. Bridgeport High,
Independence City Primary, and G.C. Foster College retain competing mapped
representations (approximately 42 m, 103 m, and 50 m apart respectively).
These are evidence conflicts, and no coordinate was averaged or snapped.

Targeted research retained null geometry for seven facilities:

- Assembly of Righteousness: no Nominatim result and no authoritative location;
- Bethel Gospel Assembly: a differently named church was rejected;
- Clifton Basic School: ECC corroborates identity/locality, but no defensible
  coordinate was found;
- Glad Tidings Church: later official shelter evidence corroborates identity,
  but a differently named church result was rejected;
- HEART College of Construction Services: official institutional identity is
  corroborated; a commercial discovery point and an OSM road result were
  rejected;
- Hellshire United Pentecostal Church: official lists conflict on facility
  naming/address and no defensible coordinate was found;
- Southborough Primary School: official address evidence is corroborated, but
  the Nominatim result was only Augusta Drive and was rejected.

The four priority-supported facilities still lacking defensible coordinates are
Assembly of Righteousness, Clifton Basic School, HEART College of Construction
Services, and Southborough Primary School. The two records printed outside the
Portmore section remain candidates until later spatial classification.

## Priority interpretation

The printed Priority Shelter cells and their unusual placement are unchanged.
A `(Priority)` marker in the same printed Shelter Name cell supports the current
interpretation. A populated Priority Shelter cell alone does not. The
`Kensington` value remains on the Independence City Primary row and is not
silently reassigned.

The review contains nine `priority_supported`, eight
`not_indicated_by_source`, and three `unresolved` candidates.
`not_indicated_by_source` means only that affirmative priority evidence was not
printed in the applicable source-name field; it must never be interpreted as
confirmed non-priority.

## Review artifacts

The identity crosswalk and identity, duplicate, location, rejected-location,
and priority review queues are under `metadata/external_sources/`. They contain
factual derivatives and review metadata only, with no source PDF pages,
screenshots, layout reproductions, embedded document content, or extended
verbatim passages.
