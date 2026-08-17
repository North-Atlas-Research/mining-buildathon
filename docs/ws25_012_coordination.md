# WS25-012 human coordination

This thin coordinator consumes WS25-010 decisions and WS25-011 replanning directly. It requests a constrained structured operator status for an upstream-active route; it never parses prose, infers closure from rainfall, selects a route/shelter, or executes an action autonomously.

For Passage Fort Drive (OSM way 630666205), frozen `open_with_concern` triggers an operator-status request while the route remains valid. A trusted synthetic `confirmed_closed` replay observation is passed to WS25-010, then the returned `closed` decision is passed to WS25-011. The resulting same-shelter reroute, capacity, reasons, evidence, and provenance are preserved. Every outcome ends `human_review_required`; the closure and all scenario inputs remain synthetic/replay assumptions, not historical claims.
