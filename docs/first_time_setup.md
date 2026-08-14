# First-Time Setup

## 1. Prepare the external SSD

Use APFS (Encrypted) and dedicate it to this project.

Suggested host layout:

```text
ProjectSSD/
├── Project/
├── Data/
│   ├── Raw/
│   ├── Interim/
│   ├── Processed/
│   ├── Outputs/
│   ├── Scratch/
│   └── Cache/
├── Docker/
└── Backups/
```

## 2. Put this repository under `Project/`

Codex should open/select the repository directory only, not `ProjectSSD/`.

## 3. Initialize data directories

From the repository:

```bash
./scripts/init_external_data_dirs.sh /Volumes/ProjectSSD/Data
```

Adjust the volume name if different.

## 4. Configure mounts

```bash
cp .env.example .env
```

Edit only `PROJECT_DATA_HOST` to match the external SSD path.

Never commit `.env`.

## 5. Bootstrap the development container

The first Docker build requires network access.

With VS Code, choose **Reopen in Container**, or use Docker Compose directly.

Verify:

```bash
python scripts/check_environment.py
pytest
ruff check .
```

The environment check should report:
- `Raw`: exists and not writable;
- other project data directories: writable.

## 6. Routine closed mode

After dependencies are installed, launch routine sessions without container network access:

```bash
docker compose -f docker-compose.yml -f docker-compose.offline.yml up -d
```

Enable network only for a bounded, approved acquisition/dependency task.

## 7. Git

Create the private GitHub repository and protect `main`.

Suggested initial branch:

```bash
git checkout -b chore/bootstrap-repository
```

Commit the starter structure through a pull request rather than committing directly to `main`.

## 8. First implementation task

Do not begin by downloading all datasets.

The recommended first Codex task is to implement and test the raw-data provenance/checksum manifest utility. This validates:
- external mounts;
- raw read-only behavior;
- project paths;
- tests;
- metadata conventions;
- the Codex task/PR workflow.

Only after that foundation is verified should acquisition begin.
