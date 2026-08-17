# WS25-011 deterministic replanning

WS25-011 consumes WS25-010 edge states directly: `open` and `open_with_concern` traverse; `uncertain` costs 1.5x; `restricted` costs 2x; `closed` is excluded. No rainfall is reinterpreted and no LLM participates. The hierarchy is baseline validation, same-shelter reroute, alternative feasible shelter by cost then stable ID, then `no_feasible_plan`.

The real replay uses Passage Fort Drive OSM way `630666205`, route `route_98b39…`, Passage Fort community, and Portsmouth Primary School. The WS25-010 concern preserves its 661.70 m baseline. The synthetic trusted closure invalidates it and produces a same-shelter 6,690.54 m reroute. It is not a claimed October closure.

Demand is explicitly scenario-only: ceil(projected population × 0.001). Exact event-day capacity is unavailable, so the replay uses nominal scenario capacity of 20 people per candidate; this is not observed capacity. No congestion, flood depth, probability, simulation, generalized optimization, or autonomous planning is implemented.
