# WS25-010 — Deterministic accessibility-state replay

## Objective and scope

WS25-010 supplies the smallest deterministic contract linking frozen WS25-009
IMERG rainfall context, explicitly labelled replay context, and trusted road
observations to graph-edge accessibility states. It is an input contract for a
future router; it does not modify the WS25-008 planner.

This is not a hydrological or flood model. In particular, its rainfall
thresholds do not confirm road flooding, closure, flood depth, or road-failure
probability.

## Evidence and precedence

Evidence remains separate in every output record:

1. Frozen native-cell IMERG 3-hour and 6-hour context (`frozen_ws25_009_imerg_context`).
2. A replay-only context flag (`scenario_assumption`), never an authoritative
   susceptibility product or observed flood record.
3. A trusted operator observation: `confirmed_open`, `restricted`, or
   `confirmed_closed`; otherwise `unknown`.

The decision order is trusted explicit observation, environmental/context
inference, then the conservative no-constraint default. Environmental evidence
can only yield `open_with_concern`; it never independently yields `restricted`
or `closed`. An observation override retains the rainfall and scenario evidence
in the decision record.

## States and routing contract

| State | Routing treatment |
| --- | --- |
| `open` | usable, multiplier 1.0 |
| `open_with_concern` | usable, multiplier 1.0, review required |
| `uncertain` | usable, multiplier 1.5, review required |
| `restricted` | usable, multiplier 2.0, review required |
| `closed` | unusable, review required |

The default is `open`, meaning no known operational restriction—not a confirmed
assessment of safety. `uncertain` is reserved for a future explicit uncertain
observation/context rather than silently turning all no-evidence roads into a
constraint.

## Rainfall rule

The transparent demo concern rule needs both a scenario-context flag and either
3-hour rainfall at least 10 mm or 6-hour rainfall at least 20 mm. Those values
are fixed operational/demo thresholds for this replay only; they were not
calibrated as hydrological thresholds. Missing rainfall therefore cannot create
a closure.

Rainfall is retrieved only through WS25-009 `rainfall_lookup`, preserving its
native containing-cell and end-labelled timestamp semantics.

## October replay candidate

The builder checks real frozen directed edge
`a1e99eb85ea1eb458f99a8130c2f3e3d5c121762cea8d70b960c31a8a0f5c960`, a
secondary Passage Fort Drive edge (OSM way `630666205`) used by baseline route
`route_2ae27a4e32ad674580c132eedb98f11ce088440a57cf87c487dc48305c5901f9`.
At 2020-10-05T17:00:00Z, the explicitly scenario-labelled context produces
`open_with_concern`. A separate synthetic trusted-operator `confirmed_closed`
record changes the operational state to `closed`; because that edge occurs on
the existing route, the recorded consequence is that the baseline route needs
replanning. Neither record claims that October 2020 actually closed this road.

## Outputs and limits

`scripts/build_portmore_accessibility_state.py` writes only generated outputs
under `/workspace/data/Outputs/ws25-010/`: two replay records plus validation
and lineage JSON. Each record includes the graph ID, timestamp, state,
environmental concern, observation, reason codes, 3h/6h values and lookup
provenance, scenario evidence, and routing semantics.

No Raw data is changed. WS25-010 adds no DEM, drainage, flood modelling,
learned model, new acquisition, November inspection, or synthetic graph edge.
