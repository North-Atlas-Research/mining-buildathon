# Mining Sprint Agent Instructions

## Mission

Implement the project safely, reproducibly, and incrementally.

This repository is part of a disaster-coordination hackathon project. The current implementation priority is the Portmore 2020 Data & Historical Replay workstream.

## Repository Boundary

- Work only inside this repository and explicitly mounted project data paths.
- Do not access personal files, host credentials, password stores, SSH keys, or unrelated directories.
- Do not expand the working directory to the external SSD root.
- Do not mount or access the host Docker socket unless explicitly approved.

## Scope

Follow the current workstream scope documented in `docs/project_scope.md`.

Do not introduce:
- AI-agent implementation;
- shelter optimization;
- hydrodynamic flood modelling;
- national-scale expansion;
- unrelated infrastructure.

unless the active task explicitly requires it.

## Data Integrity

Raw datasets are immutable.

Never:
- modify raw datasets;
- delete raw datasets;
- rename raw datasets;
- move raw datasets;
- overwrite source files.

Raw data must be mounted read-only.

Generated artifacts may be written only to:
- `Interim/`;
- `Processed/`;
- `Outputs/`;
- `Scratch/`;
- `Cache/`.

Every acquired raw dataset should have provenance metadata and a SHA-256 checksum recorded in the data manifest.

## Evaluation Integrity

October 5–7, 2020 is the development/calibration event.

November 2–10, 2020 is the held-out transfer/evaluation event once October logic is frozen.

Do not:
- tune thresholds using November outcome evidence;
- inspect November outcome labels to improve October-derived logic;
- alter algorithms in response to held-out November results without explicitly recording that held-out status has been invalidated.

Any intentional use of November evidence during development must be documented.

## Assumptions

- Do not make consequential assumptions.
- For minor implementation details, use the safest reasonable assumption and document it.
- Ask before decisions that alter requirements, architecture, data integrity, evaluation methodology, or security.

## Git Workflow

- Never commit directly to `main`.
- Work on a feature branch.
- Keep commits focused and descriptive.
- Never force-push or rewrite Git history unless explicitly instructed.
- Prefer pull requests into `main`.

Suggested branch prefixes:
- `feat/`
- `fix/`
- `data/`
- `docs/`
- `test/`

## Code Changes

- Prefer small, incremental changes.
- Preserve established interfaces where practical.
- Prefer modifying existing code over unnecessary rewrites.
- Do not change architecture without an explicit task requiring it.
- Do not remove functionality without documenting the reason.

## Testing and Validation

Before declaring a task complete:

- run relevant tests;
- run formatting/linting checks when configured;
- resolve failures caused by the change;
- report pre-existing failures separately;
- validate generated geospatial artifacts where applicable.

For data pipelines, validation should include appropriate checks such as:
- CRS;
- geometry validity;
- expected row counts;
- required columns;
- null-rate sanity checks;
- spatial bounds;
- timestamp ranges;
- checksums/provenance.

## Security

Never expose:
- API keys;
- tokens;
- passwords;
- SSH keys;
- certificates;
- private credentials.

Never put secrets in:
- source code;
- logs;
- documentation;
- commits.

Use environment variables or approved secret mechanisms.

## Internet / External Services

Default to no network access.

Network use should be limited to explicitly approved purposes such as:
- package installation;
- dependency resolution;
- official documentation;
- approved public APIs;
- approved project datasets.

Never upload project data to external services without explicit approval.

Prefer authoritative sources over mirrors.

## Destructive Operations

Do not perform destructive or broad operations without explicit approval, including:
- recursive deletion;
- mass rename;
- bulk overwrite;
- repository-wide generated-file replacement.

Explain why a destructive action is needed before performing it.

## Infrastructure Changes

Do not modify:
- Docker configuration;
- dev-container configuration;
- CI/CD;
- deployment configuration;
- authentication;
- cloud infrastructure;

unless the active task explicitly requires it.

## Reproducibility

- Pin Python dependencies.
- Keep environment changes documented.
- Prefer deterministic scripts over undocumented manual transformations.
- Put region/event parameters in configuration files rather than hard-coding them.
- Record source URLs, versions/dates, licenses, download timestamps, and hashes.

## Project Documentation

Consult:
- `docs/project_scope.md`
- `docs/data_policy.md`
- `docs/workflow.md`
- `configs/regions/portmore_2020.yaml`
- `configs/events/october_2020.yaml`
- `configs/events/november_2020.yaml`

## Completion Report

When finishing a task, report:

1. Summary
2. Files changed
3. Tests/validation run
4. Results
5. Risks or limitations
6. Assumptions
7. Recommended next step

Do not claim completion unless the task has been verified.
