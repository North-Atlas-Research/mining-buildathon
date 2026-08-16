# WS25-008 evacuation-route baseline

Historical official evacuation-route evidence is retained for reference and evaluation. Operational baseline routing for the October 2020 replay is network-derived from the canonical historical road graph and is not represented as an official evacuation route.

The April 2000 Portmore plan is `historical_municipal_explicit`; it is official historical planning evidence, not a confirmed October 2020 operational framework. The October 2011 Waterford CDRM plan is `community_plan_explicit`; its explicit local routes have unresolved 2020 currentness.

`network_baseline` routes use directed WS25-007 topology and projected metric road length only. They respect the frozen graph's one-way, access, roundabout, and temporal-edge policy, and carry a deterministic SHA-256 identity based on graph identity, origin, destination, and cost policy. They are network-derived, not official, and not confirmed event-day routes.

Community polygons attach at their nearest source-geometry point to the nearest canonical edge (not an interior representative point); shelters attach from their canonical point geometry. Both then select the nearest canonical endpoint deterministically. Connectors retain original geometry references. Shelters use the graph-specific 95 m routine and 110 m outer diagnostic thresholds; those thresholds are not universal location tolerances. One 107.517 m Cumberland High School connector was reviewed and accepted as an exception under the frozen 110 m outer threshold; the routine threshold remains 95 m. Directed non-reachability is an expected result where canonical endpoints occupy distinct strongly connected components; reverse reachability is diagnostic only. Cromarty remains an unresolved component condition: no synthetic graph connection is made and unavailable routes remain unavailable.

This work excludes rainfall, flood accessibility, closures, November evidence, shelter capacity, demand, allocation, optimization, UI, and agent logic. Historical route reconstruction is admitted only where named sequence, matching, topology, and directionality are defensible; otherwise it remains review-only.
