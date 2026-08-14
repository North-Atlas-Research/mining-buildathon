# Mining Sprint

Hackathon repository for the Portmore, Jamaica rainfall-aware disaster coordination MVP.

The immediate implementation scope is **Workstream 25 — Data & Historical Replay**.

## Development model

- Host: macOS
- Project storage: dedicated encrypted external SSD
- Runtime: Docker / VS Code Dev Container
- Source control: private GitHub repository
- Agent implementation worker: Codex
- Raw datasets: external to Git and mounted read-only

## Repository

```text
src/                 reusable Python package
scripts/             command-line data acquisition/processing utilities
tests/               automated tests
notebooks/           exploration only; production logic belongs in src/
configs/             region and event configuration
docs/                architecture, scope, workflow, provenance guidance
metadata/            tracked metadata templates/manifests, not large datasets
.devcontainer/       reproducible development environment
```

See `docs/workflow.md` before beginning implementation.
