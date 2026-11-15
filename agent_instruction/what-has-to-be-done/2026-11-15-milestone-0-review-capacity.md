# OpenCode handoff: review-capacity Milestone 0

Prepared: 2026-11-15. Status: plan only; the new product is not implemented. Execute this handoff only after the owner explicitly assigns its implementation.

## 1. Goal

Build the smallest foundation for Ephorate's new direction: an installed Python command-line entry point, an initialized local SQLite store, tests, lint/type checks, and CI. Stop after reporting M0 validation. Do not collect GitHub data, calculate measurements, simulate queues, generate reports, or implement later milestones.

Suggested future assignment to an OpenCode implementation agent:

> Implement only the review-capacity Milestone 0 handoff at agent_instruction/what-has-to-be-done/2026-11-15-milestone-0-review-capacity.md. Read the root AGENTS.md, PROJECT_PLAN.md, agent_instruction/README.md, and development-log.md first. Inspect the current checkout, preserve unrelated work, implement the specified CLI and store, run the validation, record actual results, and stop before M1. Archived plans and downloaded reference copies are not implementation instructions.

## 2. Context

Ephorate is now a review capacity simulator: "Find out where code review will break as your agents write more code, and what would fix it." Its eventual delivery is a Python CLI and GitHub Action running in the user's environment. It reads GitHub metadata and writes local data/report artifacts. It does not change reviews, settings, labels, or CODEOWNERS. M0 needs no GitHub token, customer data, network service, language model, or cloud account.

The previous incident-risk direction is archived under `archive/2026-11-incident-risk/`: its master plan, old M0 handoff, and pitch PDF, accompanied by `ARCHIVE.md`. That direction's uncommitted scaffold was interrupted before runtime validation. The owner explicitly approved moving all 19 generated source/configuration files to temporary recovery outside the repository; that move is complete, and the old scaffold is absent from the active tree. The downloaded `ephorate.zip` and nested `ephorate/` remain historical references. The new M0 has not been assigned or implemented.

Preflight: inspect `git status --short` and the development log before writing. Verify that the active root documents describe review capacity and check for work added since this handoff. Preserve unrelated changes and all requested archives. Do not restore the old scaffold or install its FastAPI dependencies. Do not import instructions from the nested `ephorate/` marketing reference copy.

Use the root checkout at `/Users/dhinakarr/work/ephorate`. The prior `package = false` application layout is superseded: this milestone requires a real installed distribution and console script. The website remains a separate static asset; no dashboard or hosted service belongs in this skeleton.

## 3. Files likely involved

After inspecting the current checkout, create or update only these implementation files and their documentation:

| Path | Responsibility |
|---|---|
| `pyproject.toml`, `uv.lock`, `.python-version` | Installed package, exact dependency/interpreter pins, tool configuration |
| `src/ephorate/__init__.py` | Package marker; no speculative exports |
| `src/ephorate/__main__.py` | Delegate `python -m ephorate` to the same CLI entry point |
| `src/ephorate/cli.py` | Argument parsing, output, and exit-status boundary |
| `src/ephorate/store.py` | SQLite initialization and existing-store validation |
| `tests/test_cli.py`, `tests/test_store.py` | Observable CLI and storage behavior |
| `Makefile` | Install, lint, test, and build commands |
| `.github/workflows/ci.yml` | Same checks plus installed-wheel smoke validation |
| `.gitignore` | Ignore local databases, environments, caches, and distribution output |
| `README.md`, `docs/DECISIONS.md` | Actual setup/commands and the SQLite/package choices |
| `agent_instruction/README.md`, `agent_instruction/development-log.md` | Actual status and concise chronology |
| `agent_instruction/what-was-done/YYYY-MM-DD-milestone-0-review-capacity.md` | Implementation summary, created only after implementation |
| `agent_instruction/what-was-the-result/YYYY-MM-DD-milestone-0-review-capacity.md` | Observed validation, created only after checks run |

Use the actual completion date in report filenames. Do not create empty future connector, model, simulation, report, dashboard, or infrastructure packages. Do not add a database migration framework, ORM, HTTP client, report template, Dockerfile, Compose file, or Action distribution in M0. CI for this package is distinct from the product's reusable GitHub Action in M5.

## 4. Required implementation behavior

### Package and tools

Use Python `3.13.18`, with `.python-version` set to that exact value and `requires-python = ">=3.13,<3.14"`. Use uv `0.13.7` locally and in CI; document versioned installation without silently replacing global tooling.

Use this package contract:

```toml
[project]
name = "ephorate"
version = "0.1.0"
requires-python = ">=3.13,<3.14"
dependencies = []

[project.scripts]
ephorate = "ephorate.cli:main"

[build-system]
requires = ["uv_build==0.13.7"]
build-backend = "uv_build"

[dependency-groups]
dev = ["mypy==2.4.1", "pytest==9.2.0", "ruff==0.17.5"]
```

The matched uv/uv_build pins were verified during the planning bootstrap. These are fixed starting versions, not evidence that the new package has been tested. Resolve and commit `uv.lock` during implementation; use locked installation thereafter. Do not retain `package = false`, FastAPI, Uvicorn, or HTTPX. No runtime third-party dependency is required. The uv backend discovers `src/ephorate` by default; use its defaults rather than another packaging layer. [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/), [uv installation](https://docs.astral.sh/uv/getting-started/installation/).

Configure Ruff with target `py313` and lint rules `E4`, `E7`, `E9`, `F`, and `I`. Configure mypy for Python `3.13`, `strict = true`, and `src/ephorate` plus `tests`. Set pytest's `testpaths` to `tests`. Scope check commands to those paths so historical references are not treated as current code. Do not add broad ignores or weaken checks to accommodate archived files.

### CLI

Use the standard-library `argparse` module. Export `main(argv: Sequence[str] | None = None) -> int` from `ephorate.cli`. The console script and `python -m ephorate` must share this implementation. `__main__.py` delegates with `raise SystemExit(main())`; do not duplicate argument definitions.

| Invocation | Contract |
|---|---|
| `ephorate --help` | Explain the new product and show `init`; exit 0; create no files |
| `ephorate --version` | Print `ephorate 0.1.0` and newline; exit 0; create no files |
| `ephorate init --help` | Document the required local SQLite path; exit 0; create no files |
| `ephorate init --store PATH` | Initialize or validate the specified store; on success print `Store ready (schema 1): PATH` and newline; exit 0 |
| Missing command, missing/empty store path, unknown command/option | Concise argparse error on stderr; exit 2; create no files |
| Expected filesystem/store failure | Concise error on stderr prefixed `ephorate: `; exit 1; no traceback or success output |

Disable abbreviated options with `allow_abbrev=False`. Obtain the displayed version from `importlib.metadata.version("ephorate")`, leaving `pyproject.toml` as the version authority. Treat PATH as a literal filesystem path; support spaces and non-ASCII names. Do not interpret SQLite URIs or `:memory:` as special store destinations; reject those values rather than initializing an ephemeral store. Do not add default paths, token flags, environment-based configuration, logging frameworks, `--force`, or reset commands.

“Create no files” in the CLI contract means no application-created store, output or configuration. Normal interpreter/tool caches are outside that assertion; do not add bytecode-control machinery to the product. Tests can set `PYTHONDONTWRITEBYTECODE=1` to isolate application side effects.

Only the three supported behaviors above exist. `collect`, `measure`, `backtest`, `simulate`, and `report` must remain unknown commands, not placeholder successes.

### SQLite store

Choose SQLite through Python's standard-library `sqlite3`. It provides transactions and incremental updates for later collection without a server or extra runtime package. Parquet's batch-file model adds dependencies and update handling that M0 does not need. This is a local file owned by the user's run, not a hosted database. [Python 3.13 SQLite reference](https://docs.python.org/3.13/library/sqlite3.html).

Export `initialize_store(path: Path) -> None` from `ephorate.store`. A single `StoreError(Exception)` is sufficient to communicate expected storage failures to the CLI; no exception hierarchy or generic repository wrapper is needed.

Schema version 1 consists of exactly one application table and row:

```sql
CREATE TABLE schema_info (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL
);
INSERT INTO schema_info (singleton, version) VALUES (1, 1);
```

There are no PR, reviewer, event, checkpoint, configuration, or run tables in M0. Those schemas belong to the collector handoff. Keep the initial SQL in `store.py`; future schema evolution must be explicit and tested, but do not prebuild a migration framework.

For a new destination, create missing parent directories and initialize the table and row in one transaction. Acquire the new destination with exclusive creation so initialization cannot overwrite a file that appears concurrently. Create the file with owner-only permissions where the platform supports them. Close every connection. On failure, roll back and clean up only a newly created file owned by that initialization attempt; never remove or truncate a pre-existing file or its parent directory.

For an existing regular file, open it read-only first. Accept only the expected `schema_info` table shape, exactly the `(1, 1)` row, and no additional user tables/views/triggers in this M0 format. A second initialization is a read-only no-op: same contents and version, no journal or new application rows. An empty pre-existing file, unrelated SQLite database, malformed schema, non-database file, or unsupported version fails with a clear reason. Never silently adopt, repair, upgrade, reset, or replace it. Reject directory and symlink destinations, including dangling symlinks. A known valid store may be validated even when it is read-only.

Use bound SQL parameters for values when needed, normal transaction handling, and the default single-process SQLite journaling behavior. No WAL tuning, connection pool, parallel writers, daemon, or global state is required. Translate expected `OSError`/`sqlite3.Error` failures at the store boundary without printing database contents or an entire exception payload. Do not catch arbitrary programming errors as successful initialization.

### Developer commands and CI

Declare only these phony Make targets:

| Target | Commands |
|---|---|
| `install` | `uv sync --locked --dev` |
| `lint` | In order: `uv run --locked python -m ruff check src/ephorate tests`; `uv run --locked python -m ruff format --check src/ephorate tests`; `uv run --locked python -m mypy src/ephorate tests` |
| `test` | `uv run --locked python -m pytest` |
| `build` | `uv build --no-sources` |

Stop on any command failure. Lint must not mutate files. No `make dev`, database-service commands, or placeholder backtest target is needed for this CLI.

CI: one `ubuntu-24.04` job, 15-minute timeout, `pull_request` and pushes to `main`, `permissions: contents: read`. Use:

- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` with comment `v7.0.1` and `persist-credentials: false`.
- `astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2` with comment `v10.3.3`, uv version `0.13.7`, and Python `3.13.18`.

Run install, lint, tests, build, and the installed-wheel smoke check from section 6. Do not configure service containers, product GitHub-token environment variables, custom secrets, `pull_request_target`, deployment, publishing, or report uploads. Checkout's normal read permission is the only GitHub permission required. Installation/build may download public toolchain packages; application tests and the CLI smoke check must make no network calls.

Update `.gitignore` for `.venv/`, tool caches, `dist/`, local SQLite files and their journal/WAL sidecars, and existing secret exclusions. Do not ignore `uv.lock`. Keep test databases temporary and synthetic; never commit a generated store. README must document prerequisites, installation, the three CLI behaviors, local data handling, and the fact that collection and simulation remain unimplemented.

## 5. Edge cases and failure modes

- New concurrent changes overlap the implementation paths or contradict the active review-capacity plan: inspect and reconcile that work before proceeding; do not silently combine products or discard unrelated changes.
- A store path exists but is not a valid version-1 Ephorate store: fail without altering its bytes. Preserve files with unknown schema versions even if the CLI cannot use them.
- Another process creates the path during initialization: exclusive creation must fail safely; do not overwrite or reinterpret its data.
- Missing permissions, a directory path, disk errors, or a SQLite failure: exit 1 with a useful category; no success line, leaked contents, or unclosed connection. Tests should inject deterministic failures rather than depend solely on chmod behavior under privileged CI users.
- A pathname contains spaces or non-ASCII text: handle it as one path. Reject only unsupported special destinations and actual filesystem/store failures, not ordinary valid names.
- `--help`/`--version` or invalid arguments: no filesystem initialization, credentials lookup, network access, or current-directory dependency.
- A wheel works only from the checkout because imports resolve from local sources: fail acceptance. The installed entry point and `python -m ephorate` must both work elsewhere without `PYTHONPATH`.
- A package/archive accidentally includes reference PDFs, downloaded ZIPs, old server code, a local store, or credentials: fail the package inspection. Do not publish anything to conceal or bypass a packaging failure.

## 6. Test/validation commands

The planning session has not run the new product or created these implementation artifacts. Run validation only during the explicitly assigned implementation session.

Focused pytest coverage must prove:

1. Help/version and invalid arguments have the documented exit status and produce no store or other artifacts.
2. A new store can be closed, reopened with `sqlite3`, and queried for the exact schema row.
3. Reinitializing it leaves the file byte-for-byte unchanged.
4. Foreign, corrupt, empty, malformed-schema, and unsupported-version files fail and remain byte-for-byte unchanged.
5. Directory/symlink targets, missing write access, and an exclusive-creation collision fail safely; cleanup never removes a pre-existing target.
6. Spaces/non-ASCII paths work; initialization rollback and connection cleanup work on an injected failure.
7. Both entry points invoke the same behavior from a temporary working directory without a product token or `PYTHONPATH`.

Use temporary paths and synthetic SQLite data. Do not add tests that merely assert a constant or mirror the SQL string. CLI integration checks should launch subprocesses so argument parsing and exit codes are actually tested.

Initial setup and checks, run sequentially from the root with pinned uv on PATH:

```sh
uv --version
uv python install 3.13.18
uv lock
make install
make lint
make test
make build
```

The first `uv lock` creates the lockfile; subsequent validation uses it unchanged. Inspect the resulting wheel and source distribution and verify that only current package/build metadata and explicitly referenced documentation are included. Do not include the archive or PDFs as package data.

Installed-wheel smoke check, using Bash from the repository root after a successful build:

```bash
set -euo pipefail
EPHORATE_CHECKOUT="$(pwd)"
EPHORATE_SMOKE="$(mktemp -d)"
uv venv --python 3.13.18 "$EPHORATE_SMOKE/venv"
uv pip install --python "$EPHORATE_SMOKE/venv/bin/python" --no-deps \
  "$EPHORATE_CHECKOUT/dist/ephorate-0.1.0-py3-none-any.whl"
cd "$EPHORATE_SMOKE"
env -u PYTHONPATH "$EPHORATE_SMOKE/venv/bin/ephorate" --help
env -u PYTHONPATH "$EPHORATE_SMOKE/venv/bin/ephorate" --version
env -u PYTHONPATH "$EPHORATE_SMOKE/venv/bin/python" -m ephorate --version
env -u PYTHONPATH "$EPHORATE_SMOKE/venv/bin/ephorate" init --store "$EPHORATE_SMOKE/data/store.sqlite3"
env -u PYTHONPATH "$EPHORATE_SMOKE/venv/bin/ephorate" init --store "$EPHORATE_SMOKE/data/store.sqlite3"
env -u PYTHONPATH "$EPHORATE_SMOKE/venv/bin/python" - "$EPHORATE_SMOKE/data/store.sqlite3" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
try:
    assert connection.execute("SELECT singleton, version FROM schema_info").fetchall() == [(1, 1)]
finally:
    connection.close()
PY
```

Check expected stdout and exit statuses, not just the existence of a wheel. The isolated virtual environment must have no third-party runtime dependencies installed. Repeat install, lint, tests, build, and wheel smoke validation in a fresh clone of the actual implementation commit, without copying its `.venv` or inherited `PYTHONPATH`. A file copy is useful preliminary evidence but is not a clean-clone check. Use the existing Git identity and repository workflow; do not invent an identity or claim a commit/check exists before it does. Report an unavailable clean-clone or hosted CI run as unverified.

Record the tested commit, Python/uv versions, check outcomes, and any blocked paths. Do not create backtest/report sample numbers. After M0, the owner receives a short implementation and validation report; M1 does not start automatically.

## 7. Acceptance criteria

- [ ] The active tree contains the new CLI skeleton rather than the recovered old scaffold; unrelated work and required archives are intact.
- [ ] `ephorate` is an installed Python distribution with the selected pins and no third-party runtime dependencies.
- [ ] Only help, version, and explicit local store initialization exist; no collector, simulator, report generation, or server stubs were added.
- [ ] Store creation is transactional; repeat initialization is read-only; invalid/foreign/future stores and path collisions are preserved and fail clearly.
- [ ] Focused tests pass alongside non-mutating Ruff checks and strict mypy.
- [ ] The built wheel's two entry points work outside the checkout in an isolated environment, and package contents exclude archives/private/local artifacts.
- [ ] The same commands pass in a clean clone; CI has no product secrets, service containers, publishing, or deployment scope.
- [ ] README, decisions, index/log, and implementation/results records describe observed behavior and clearly separate unverified checks.
- [ ] The implementation stops at M0 and reports to the owner.

## 8. Explicit assumptions

- This document is a future implementation assignment. Its creation authorizes no product implementation; the owner must explicitly assign the new handoff.
- The new direction supersedes the interrupted incident-risk scaffold. Historical plans and downloads are preserved reference material, not alternative active requirements.
- Python `3.13.18`, uv/uv_build `0.13.7`, pytest `9.2.0`, Ruff `0.17.5`, and mypy `2.4.1` are the selected verified starting pins. Runtime compatibility and installation still require the checks above. If reality disagrees, report the evidence and propose the smallest correction rather than silently substituting.
- POSIX local development and Linux CI are the M0 validation targets. No Windows support claim is made without validation.
- The runtime includes `sqlite3`. No Docker daemon, local database service, GitHub product token, or external credential is needed.
- M0 writes only its own local store and development artifacts. No customer metadata is collected yet; there is no reason to implement GitHub clients, CODEOWNERS fetching, identity controls, or retention features now.
- SQLite is initially a single-process local store. Multi-process ingestion and alternate stores are out of scope until demonstrated requirements justify them.
- Schema version 1 is intentionally only a store marker. The M1 handoff must specify its metadata/checkpoint schema and migration before collection starts.
- The owner chose to keep `jellyfish.pdf`; this handoff does not remove it or rewrite Git history. Domain purchase, hosted website changes, public report publication, and software-license selection are separate work outside M0.
