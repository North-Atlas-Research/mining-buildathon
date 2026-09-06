# Mining Sprint

Rainfall-aware disaster coordination MVP for **Portmore, Jamaica**, demonstrating how historical rainfall context, structured human input, deterministic accessibility state, evacuation replanning, and human review can be combined without treating rainfall alone as proof of road closure or executing operational actions automatically.

The completed MVP is demonstrated through an **October Passage Fort replay**.

## What the MVP demonstrates

The canonical integrated replay is:

```text
historical October rainfall/context
        ↓
open_with_concern
        ↓
active Passage Fort evacuation route affected
        ↓
structured operator confirmation required
        ↓
synthetic confirmed_closed
        ↓
closed
        ↓
baseline route invalidated
        ↓
rerouted_same_shelter
        ↓
scenario capacity consequence
        ↓
human_review_required
```

The workflow preserves a strict distinction between measured context, inference, synthetic replay input, deterministic system outputs, scenario assumptions, and human decision-making.

No operational action is executed automatically.

## Passage Fort replay

The integrated demonstration uses the following verified scenario:

| Item                        | Result                       |
| --------------------------- | ---------------------------- |
| Community                   | Passage Fort                 |
| Road                        | Passage Fort Drive           |
| OSM way                     | `630666205`                  |
| Historical rainfall context | 13.89 mm / 3h; 28.76 mm / 6h |
| Initial accessibility state | `open_with_concern`          |
| Baseline shelter            | Portsmouth Primary School    |
| Baseline route distance     | 661.70 m                     |
| Structured replay input     | synthetic `confirmed_closed` |
| Updated accessibility state | `closed`                     |
| Replanning result           | `rerouted_same_shelter`      |
| Selected shelter            | Portsmouth Primary School    |
| Rerouted distance           | 6,690.54 m                   |
| Scenario demand             | 11                           |
| Nominal scenario capacity   | 20                           |
| Scenario remaining capacity | 9                            |
| Final coordination state    | `human_review_required`      |

The historical rainfall values provide context for accessibility concern. They do **not** independently establish that Passage Fort Drive was flooded, restricted, or closed.

The closure used in the replay is an explicitly labelled **synthetic operator input** used to exercise the deterministic downstream workflow.

## Evidence and decision boundaries

The MVP separates six kinds of information.

### Historical / measured context

Historical October rainfall data provide environmental context for the replay.

Rainfall/context may raise an accessibility concern but does not by itself establish a road closure.

### Inference

The accessibility engine may return:

```text
open_with_concern
```

This means the road remains considered traversable while concern evidence is retained.

### Synthetic replay input

The integrated replay supplies:

```text
confirmed_closed
```

as a structured synthetic operator observation.

It is not presented as a historical road observation.

### Deterministic outputs

Given trusted structured input, the accessibility and replanning components deterministically return the resulting accessibility state and route plan.

For the canonical replay:

```text
confirmed_closed
→ closed
→ rerouted_same_shelter
```

### Scenario assumptions

Demand and shelter capacity values are used only to demonstrate downstream coordination consequences.

They are scenario values, not claims about observed event-day shelter demand or operational shelter capacity.

### Human review

The workflow terminates at:

```text
human_review_required
```

The system presents evidence and deterministic project outputs for review. It does not approve, dispatch, evacuate, close roads, or otherwise execute an operational action automatically.

## Run the integrated demo

From the project development environment:

```bash
python scripts/run_integrated_demo.py
```

Then open:

```text
http://127.0.0.1:8000
```

The integrated page presents the historical context, active-plan relevance, synthetic operator replay input, deterministic accessibility update, replanning result, scenario capacity consequence, and final human-review state.

## Reproduce the underlying replay stages

The main replay stages can also be run individually:

```bash
python scripts/build_portmore_accessibility_state.py
python scripts/run_october_replanning.py
python scripts/run_october_coordination.py
```

The integrated presentation is launched with:

```bash
python scripts/run_integrated_demo.py
```

## Validation

The merged MVP is validated with:

```bash
pytest
ruff check .
git diff --check
```

Current merged-state validation:

```text
pytest:          72 passed
Ruff:            clean
git diff --check: clean
```

The integrated demo also launches successfully with:

```bash
python scripts/run_integrated_demo.py
```

## Environment and setup

Development is designed around a reproducible VS Code Dev Container environment.

Initial host-side data directory setup:

```bash
./scripts/init_external_data_dirs.sh /Volumes/ProjectSSD/Data
cp .env.example .env
```

Set `PROJECT_DATA_HOST` in `.env`, then use VS Code **Reopen in Container**.

The container setup installs the project development dependencies and `osmium-tool`.

Environment verification:

```bash
python scripts/check_environment.py
```

For full setup instructions, see [First-time setup](docs/first_time_setup.md).

Where offline container operation is applicable:

```bash
docker compose -f docker-compose.yml -f docker-compose.offline.yml up -d
```

## Repository structure

```text
src/                 reusable Python package
scripts/             command-line processing and replay utilities
tests/               automated tests
notebooks/           exploration only; production logic belongs in src/
configs/             region and event configuration
docs/                architecture, scope, workflow, provenance, and workstream documentation
metadata/            tracked metadata templates/manifests, not large datasets
.devcontainer/       reproducible development environment
```

Raw datasets remain external to Git and are mounted into the project environment.

## Completed replay components

The final integrated replay is documented across five completed Workstream 25 components.

### WS25-009 — October rainfall

[docs/ws25_009_october_rainfall.md](docs/ws25_009_october_rainfall.md)

Documents the historical IMERG rainfall source, event interval, native-grid processing, accumulation semantics, and the explicit rainfall-only evidence boundary.

### WS25-010 — Accessibility state

[docs/ws25_010_accessibility_state.md](docs/ws25_010_accessibility_state.md)

Defines evidence classes, accessibility-state precedence, concern handling, routing semantics, and the distinction between rainfall context and trusted explicit observations.

### WS25-011 — Deterministic replanning

[docs/ws25_011_replanning.md](docs/ws25_011_replanning.md)

Documents deterministic baseline-route validation, rerouting behavior, the Passage Fort result, and scenario-only capacity consequences.

### WS25-012 — Human-in-the-loop coordination

[docs/ws25_012_coordination.md](docs/ws25_012_coordination.md)

Documents structured human input, delegation to deterministic upstream components, and the terminal `human_review_required` state.

### WS25-013 — Integrated demo

[docs/ws25_013_integrated_demo.md](docs/ws25_013_integrated_demo.md)

Documents the local integrated presentation, consumed artifacts, presentation-only boundary, and textual fallback when route geometry is unavailable.

## Project documentation

Additional project documentation:

* [Project scope](docs/project_scope.md)
* [Workflow](docs/workflow.md)
* [Data policy](docs/data_policy.md)
* [Provenance guidance](docs/provenance.md)
* [First-time setup](docs/first_time_setup.md)

A [final submission summary and evidence index](docs/final_submission.md) is included with the repository.

## Demo evidence

Submission-facing screenshots and related evidence are stored under:

```text
docs/assets/ws25_013/
```

The canonical integrated-demo screenshot shows the full distinction between:

```text
historical/measured context
→ inference
→ synthetic replay input
→ deterministic update
→ scenario consequence
→ human review
```

![Passage Fort replay dashboard: historical context, synthetic closure input, deterministic reroute, and human-review outcome](docs/assets/ws25_013/passage_fort_replay.png)

## Scope and limitations

This MVP is deliberately narrower than an operational flood-management system.

It does **not** claim to provide:

* flood-depth estimation;
* hydraulic or hydrodynamic modelling;
* rainfall-derived confirmation of road closure;
* calibrated road-failure probabilities;
* observed event-day evacuation demand;
* verified operational shelter capacity;
* autonomous road closure;
* autonomous evacuation approval;
* dispatch or execution of operational actions.

The historical rainfall layer provides context. Explicit trusted observations determine restricted or closed accessibility states. Replanning is deterministic given those states. Scenario values demonstrate downstream consequences. Final action remains subject to human review.

## Development model

* Host: macOS
* Project storage: dedicated encrypted external SSD
* Runtime: Docker / VS Code Dev Container
* Source control: private GitHub repository
* Agent implementation worker: Codex
* Raw datasets: external to Git and mounted read-only

## License status

No open-source license file has been selected for this repository. Reuse or public redistribution should therefore be confirmed with the project owner before publication.

## Submission status

The technical MVP is complete.

The repository now demonstrates the intended end-to-end Passage Fort workflow while preserving evidence provenance, deterministic decision boundaries, and human oversight.

Final submission packaging consists of documentation, evidence organization, validation recording, and repository hygiene rather than additional feature development.
