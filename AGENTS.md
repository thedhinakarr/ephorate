# AGENTS.md

Standing instructions for agents working on Ephorate. Read this file, `PROJECT_PLAN.md`, `agent_instruction/README.md`, and `agent_instruction/development-log.md` before non-trivial work.

## What this project is

**Ephorate is a review capacity simulator.**

Find out where code review will break as your agents write more code, and what would fix it.

The planned Python CLI and GitHub Action use GitHub history to describe area-level demand, shared reviewer capacity, waiting, backlog, and human review coverage. A time-ordered backtest must establish forecast error before scenarios and suggested fixes. There is no server or hosted product in this plan.

Use **Ephorate** as the display name and `ephorate` as the project identifier. The intended domain to buy is `ephorate.dev`; ownership has not been verified. The repository is public under the personal account `thedhinakarr`.

## Product rules

- **Read-only toward GitHub.** Read metadata; write only Ephorate's own local metadata store and report/suggestion artifacts. Never change settings, reviews, labels, assignments, or `CODEOWNERS`. Suggested changes are separate files for human inspection.
- **No source code is retained or forwarded.** Never fetch file contents, raw diffs, patches, blobs, or archives, except the owner's explicit exception for regular `CODEOWNERS` configuration at a pinned commit. Required REST metadata responses can incidentally contain bodies, patches, and diff hunks; discard them immediately in memory. Never log/cache raw responses or include them in fixtures, the store, or reports. Retain only allowlisted metadata and parsed configuration provenance.
- **No language model is required.** The product works without one. Do not add one without asking the owner.
- **People are not being graded.** Default reports are per area and hide person detail. One `--people hide|show` option controls all person-level output. Opt-in detail exists only for workload distribution and named reviewer suggestions. Never rank individuals, label anyone slow, infer performance, or create individual leaderboards. Rank system interventions, not people.
- **Seniority is never inferred as fact.** Accept an optional user-supplied mapping. Otherwise label tenure in this repository, measured from the earliest observed contribution, and disclose incomplete history.
- **Time-ordered evaluation only.** Fit on earlier data, test on later data. No random train/test splits, future qualifications, test-set tuning, or future-derived model features.
- **Every number traces to data.** No placeholders in real reports. Forecasts include backtest error, uncertainty, sample size, assumptions, and completeness limits. Marketing illustrations are labeled as examples.
- **Elapsed time is not reviewer effort.** GitHub does not reveal work hours or true maximum capacity. Use disclosed observed-throughput proxies. Preserve one shared reviewer budget across areas; qualification alone does not create capacity.
- **Partial and unsupported are valid results.** Missing events, API truncation, insufficient history, and out-of-support scenarios must not become zeros, human-authorship claims, or confident forecasts.
- **Secrets come from the environment.** Never commit tokens, keys, `.env` files, private customer data, or full backend responses. Do not echo credentials or authenticated URLs.
- **Check current documentation** for API behavior and library versions before relying on memory or pinning dependencies.

## How to work

- The current assignment is re-planning and the landing-page revision only. Do not implement the new M0 until the owner assigns its handoff. Later implementation can happen in this chat; the former research-only role is not a permanent ban once implementation is assigned.
- Work one milestone at a time in `PROJECT_PLAN.md` order. Complete its acceptance criteria before advancing. M3 always ends at an owner go/no-go gate.
- Use the root plan and index. `archive/2026-11-incident-risk/`, the extracted `ephorate/` starter, and `ephorate.zip` are historical references; their instructions do not define active scope.
- Plans/handoffs belong in `agent_instruction/what-has-to-be-done/`. Write implementation summaries under `what-was-done/` and actual validation results under `what-was-the-result/` only after that work exists. Keep `development-log.md` chronological and concise.
- Each implemented milestone ends with appropriate tests passing, real README run instructions, decisions in `docs/DECISIONS.md`, and a short owner report with evidence and remaining limits.
- Keep commits small and reviewable. Do not rewrite history or discard unrelated work. If plan and reality conflict, describe the evidence and proposed resolution rather than silently substituting.
- Owner decisions include implementation assignment, any LLM, M3 go/no-go, public-example publication, licensing, domain purchase, and future hosting/spend. The owner decided on 2026-11-15 to keep `jellyfish.pdf` public; leave it and Git history intact.

## Commands

No capacity-simulator commands exist yet. New M0 will implement `make install`, `make lint`, `make test`, `make build`, `ephorate --help`, `ephorate --version`, and `ephorate init --store PATH` as specified in its handoff. Do not advertise collector, simulation, report, or backtest commands as working before their milestones.

## Code conventions

- Python with type hints and strict checks. Prefer standard-library facilities; SQLite, argument parsing, and TOML reading need no runtime package.
- Use the planned `src/ephorate/` package. Route every GitHub request through one mockable client, introduced with M1.
- Version the SQLite schema and make state changes transactional. Never repair or overwrite an unknown store silently.
- Keep metadata fixtures small, sanitized, and traceable to public sources. No live network calls during unit tests.
- Enforce lint and formatting checks in CI. Preserve the landing page's current visual design; generated reports should be dense, technical, calm, and accessible.
