# Development Workflow

## Roles

### Workstream conversations

Authoritative source for:
- project requirements;
- research/source review;
- architecture and interface decisions;
- acceptance criteria;
- scope control;
- validation interpretation;
- frozen decisions.

### Codex

Implementation worker for:
- repository changes;
- data-ingestion scripts;
- transformations;
- tests;
- validation utilities;
- refactoring inside approved scope.

Codex should receive bounded tasks, not broad project ownership.

### GitHub

Authoritative implementation history:
- branches;
- commits;
- pull requests;
- issues;
- test results;
- reviewed code state.

### Human operator

Final authority for:
- security approvals;
- data-source approval;
- consequential assumptions;
- merges;
- evaluation freeze;
- scope changes.

## Standard task loop

1. Define the task in the relevant workstream conversation.
2. Record any frozen decision or interface change in repository docs/config.
3. Create a GitHub issue or concise Codex task.
4. Create a feature branch.
5. Ask Codex to implement only the bounded task.
6. Codex runs tests/validation and reports results.
7. Review the diff and generated artifacts.
8. Return questionable results to the workstream conversation for interpretation.
9. Revise if needed.
10. Merge via pull request when acceptance criteria are met.

## Recommended Codex task format

Every task should state:

- **Goal**
- **Allowed files/directories**
- **Inputs**
- **Required outputs**
- **Acceptance criteria**
- **Tests/validation**
- **Do not change**
- **Relevant docs/configs**

Example:

```text
Goal:
Implement raw-file manifest generation.

Allowed:
scripts/
src/mining_sprint/
tests/
metadata/

Inputs:
Files under /workspace/data/Raw (read-only).

Output:
A manifest containing relative path, file size, SHA-256, and capture timestamp.

Acceptance:
- never modifies Raw;
- deterministic path ordering;
- tests cover empty and populated directories;
- malformed/unreadable files produce a clear error.

Do not change:
Docker, event configs, region configs.
```

## Decision rule

Do not send an unresolved design question to Codex and ask it to choose the architecture.

Resolve consequential choices in the workstream conversation first, then ask Codex to implement the decision.

## Handoff rule

When Codex discovers:
- missing source data;
- ambiguous schema;
- unexpected geospatial mismatch;
- a need to change architecture;
- evaluation leakage risk;

stop implementation of that decision and bring the finding back to the relevant workstream conversation.


## Network modes

The initial image build and dependency installation require network access.

After bootstrap, routine closed-mode development can be launched with the offline override:

```bash
docker compose -f docker-compose.yml -f docker-compose.offline.yml up -d
```

When a task legitimately requires approved data acquisition or dependency changes, use the normal compose configuration for that bounded task, then return to offline mode.

This is stronger than relying only on an instruction telling the agent not to use the network.
