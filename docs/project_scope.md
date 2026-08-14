# Workstream 25 — Data & Historical Replay

## Objective

Construct the reusable Portmore 2020 region package and event-specific historical datasets.

## In scope

- Portmore study boundary and CRS
- 2019/event-era shelter dataset
- approximately 10–20 community zones
- WorldPop 2020 population aggregation
- event-era OSM road graph
- evacuation routes
- bridge metadata where available
- Copernicus DEM and useful derivatives
- ESA WorldCover 2020
- drainage / waterways
- historical flood susceptibility
- NASA GPM IMERG replay
- October 5–7 development/calibration event
- November 2–10 held-out transfer/evaluation event
- separate historical outcome observations
- optional Sentinel-1 acquisition inventory
- static October event map
- data dictionary and provenance records

## Out of scope

- AI agent
- shelter optimization
- routing optimization beyond data/graph validation
- hydrodynamic flood simulation
- authoritative street-level flood-depth prediction
- national-scale system
- production integration

## Completion gate

Before handoff, verify:
- shelters locate reliably;
- community zones are usable;
- road graph connectivity is adequate;
- critical Waterford / Gregory Park routes exist;
- rainfall rasters align correctly;
- susceptibility aligns sensibly with documented flood locations;
- population aggregation is plausible;
- event timestamps are reproducible.
