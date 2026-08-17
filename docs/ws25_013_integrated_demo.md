# WS25-013 integrated demo

Launch with `python scripts/run_integrated_demo.py`, then open `http://127.0.0.1:8000`. It reads `/workspace/data/Outputs/ws25-012/passage_fort_coordination.json` and WS25-011 validation output. This is a presentation layer only: it performs no accessibility, routing, shelter, capacity, approval, or evacuation decisions.

It labels historical/measured context, environmental inference, synthetic replay/operator input, deterministic outputs, scenario assumptions, and human review. Route geometry is not available in the replay result, so it shows canonical textual/metric before-and-after information.
