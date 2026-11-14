# Ephorate: build and deploy plan

This plan is written for a coding agent (Codex) that will build the project with a human owner available for decisions and credentials. Read `AGENTS.md` first for the standing rules.

## 1. Goal and order of work

Build a service that scores each pull request with a calibrated probability of causing a production incident, applies a team-defined threshold, and tracks outcomes.

The work is ordered so that the riskiest assumption is tested first. That assumption is: *changes the model calls low risk really did cause fewer incidents.* Milestones 1 to 3 produce an offline backtest that answers this with no product, no GitHub App and no deployment. Only if the backtest shows signal is the live service (Milestones 4 to 7) worth building. Do not skip ahead.

### Not in scope for this plan

- Writing review comments on code quality. Customers already have AI reviewers; this product sits on top of them.
- Merging or approving pull requests automatically. The live service ships in shadow mode (it reports what it would decide). Enforcement is a later decision for the human owner.
- GitLab, Bitbucket and other incident tools. GitHub, PagerDuty and Datadog only, behind interfaces that allow more later.
- Multi-region, single-tenant and on-premise deployment.

## 2. Architecture

```
Sources                Core                          Surfaces
-------                ----                          --------
GitHub (PRs, commits)  Ingest and link incidents     Pull request check run
CI results             Signal extraction             Slack reviewer routing
PagerDuty incidents    Calibrated risk model         Escape-rate dashboard
Datadog alerts         Policy engine                 Audit log
```

Flow for one pull request:

1. A webhook reports that a pull request opened or changed.
2. Signals are extracted from the diff, the repository history and the author's and reviewers' familiarity with the touched files.
3. The model returns a probability. A calibration layer makes that probability match observed incident rates.
4. The policy file in the customer's repository decides: below threshold, or above.
5. A check run is posted with the probability, a comparison baseline and the decision. Above-threshold changes get a suggested reviewer.
6. After merge, later incidents, reverts and hotfixes are linked back to the change. These labels feed the next model refresh.

## 3. Tech stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python, FastAPI | Same language as the modelling code |
| Jobs and workflows | Temporal | Long, retryable ingestion and backfill jobs |
| State | PostgreSQL | Tenants, repos, pull requests, decisions, audit log |
| Event analytics | ClickHouse | Fast aggregation for the escape-rate dashboard |
| Code parsing | tree-sitter | Language-aware diff features |
| Incident linking | SZZ-style blame tracing, revert and hotfix detection | Standard way to tie a fix to the change that introduced the bug |
| Risk model | LightGBM, with isotonic calibration | Works on small tabular data; decisions can be explained |
| LLM features | One provider behind an interface | Semantic tags for a diff; used as model inputs only |
| Policy | YAML file in the customer repo | Versioned and reviewable alongside the code |
| GitHub integration | GitHub App, Checks API, webhooks | Least-privilege, per-installation access |
| Dashboard | Next.js, TypeScript | Standard, easy to host |
| Infrastructure | AWS, Terraform, Docker | Standard path to a SOC 2 audit later |
| CI/CD | GitHub Actions | Lint, test, build, deploy |

Confirm current versions and maintenance status of each library before pinning. If one is unsuitable, propose a replacement in `notes/DECISIONS.md` and ask before switching.

## 4. Repository layout

```
/
  AGENTS.md
  PROJECT_PLAN.md
  README.md
  Makefile
  docs/
    index.html             the public website, served by GitHub Pages
  notes/
    DECISIONS.md           choices made where the plan left room
    BACKTEST_REPORT.md     written at the end of Milestone 3
    RUNBOOK.md             written in Milestone 7
  packages/
    connectors/            GitHub, PagerDuty, Datadog clients (all mockable)
    linking/               incident-to-change linking
    signals/               feature extraction
    model/                 training, calibration, evaluation
    policy/                policy file schema and evaluation
  services/
    api/                   FastAPI app: webhooks, check runs, dashboard API
    worker/                Temporal workers: backfill, scoring, refresh
  apps/
    dashboard/             Next.js
  infra/
    terraform/
  tests/
    fixtures/              small public-repo samples only
```

## 5. Data model (core tables)

- `tenant`, `installation`, `repository`
- `change`: one row per merged commit or pull request, with author, files, timestamps
- `incident`: one row per incident, with source, start time, severity, linked service
- `change_incident_link`: which change is believed to have caused which incident, with the linking method and a confidence
- `feature_snapshot`: the exact feature values used for a score, so any decision can be reproduced
- `score`: probability, model version, calibration version
- `decision`: threshold applied, outcome, policy file hash
- `audit_event`: append-only log of every decision and every configuration change

Never update or delete rows in `feature_snapshot`, `score`, `decision` or `audit_event`. They are the evidence the product is selling.

## 6. Milestones

Each milestone lists what to build, what a person must supply, and the acceptance criteria. A milestone is done only when every criterion is met.

### Milestone 0: Project skeleton

Build:
- Repository layout above, `Makefile` targets named in `AGENTS.md`, Docker Compose for local PostgreSQL, ClickHouse and Temporal.
- CI workflow running lint, type-check and tests on every pull request.
- Empty packages with one passing test each.

Done when:
- `make install && make lint && make test` pass on a clean clone.
- `make dev` starts the API and it answers a health check.

### Milestone 1: History ingestion and incident linking (offline)

This is the foundation for the backtest. It works from a local git clone, with no GitHub App.

Build:
- A loader that walks a repository's history and writes `change` rows.
- Linking that labels which changes later needed fixing:
  - commits that revert an earlier commit;
  - bug-fix commits (identified by issue references and commit message patterns), traced back with SZZ-style blame to the commits that introduced the fixed lines;
  - hotfixes: a fix to the same files within a short window after a merge.
- A second linking path that accepts an incident export (CSV or JSON with timestamp, service and optional fix commit) and links incidents to changes. This is what design partners will supply.
- Each link stores its method and a confidence.

Why two paths: without partner data, reverts and bug fixes in public repositories are the best available stand-in for incidents. They are a proxy, so say so clearly in every report.

Done when:
- Running the loader on at least three large public repositories with good issue hygiene produces `change` and `change_incident_link` tables. Choose the repositories and record why in `notes/DECISIONS.md`.
- A manual spot check of 50 links per repository is written up with the observed precision. If precision is below roughly 70%, improve the linking before moving on.
- Unit tests cover revert detection, blame tracing and the incident import, using small synthetic repositories built in the test.

### Milestone 2: Signals

Build feature extraction for a change, using only information available at the moment the change was proposed:
- Size and shape: lines added and removed, files touched, directories spanned, share of test files.
- History: how often the touched files changed recently, how often they were involved in past linked incidents.
- Ownership and familiarity: share of the touched lines last written by the author; how many past changes the author has in those files.
- Structure (tree-sitter): kinds of constructs changed, such as function signatures, error handling, configuration, migrations.
- Path categories: authentication, payments, infrastructure, schema, dependencies, documentation, tests. Make the mapping configurable.
- Timing: day and hour, proximity to a release.
- LLM tags (optional, behind a flag): a small fixed set of labels describing the intent of the diff. Cache results. The pipeline must work with this flag off.

Done when:
- Features are produced for every change from Milestone 1 and stored in `feature_snapshot`.
- A test proves there is no leakage: recomputing features for a change after later commits are added gives identical values.
- A data dictionary in `notes/` lists each feature and how it is computed.

### Milestone 3: Model, calibration and backtest report

Build:
- Training with LightGBM on a time-based split: train on the earliest portion, calibrate on the next, test on the most recent.
- Isotonic calibration fitted on the calibration window only.
- Evaluation on the test window:
  - reliability curve and calibration error;
  - incident rate by risk band (lowest third, middle third, highest third);
  - the share of changes that could skip review at several thresholds, and the incident rate among them;
  - comparison against two simple baselines: change size alone, and path category alone.
- `make backtest REPO=...` runs the whole pipeline end to end and writes `notes/BACKTEST_REPORT.md` with tables and charts.

Done when:
- The report exists for each test repository and states plainly whether the lowest-risk third of changes had a lower rate of linked problems than the overall rate, and by how much, with confidence intervals.
- The model beats both simple baselines, or the report says it does not.
- Results are reproducible from a fixed seed.

**Stop here and report to the human owner.** The decision to continue depends on these results. If the model shows no useful separation, propose what to change (better linking, more signals) and do not start Milestone 4.

**HUMAN:** review the backtest report; arrange design-partner data if available; decide go or no-go.

### Milestone 4: GitHub App and live scoring in shadow mode

**HUMAN:** register a GitHub App with these permissions and supply its ID, private key and webhook secret: read access to contents, pull requests, metadata and checks history; write access to checks only. Subscribe to pull request, push and check suite events.

Build:
- Webhook endpoint with signature verification and idempotent handling of redelivered events.
- On installation, a Temporal workflow that backfills history for the selected repositories using Milestones 1 and 2, then trains a first model for that tenant. Respect API rate limits.
- On each pull request event, a scoring workflow: extract signals, score, calibrate, evaluate policy, store `feature_snapshot`, `score` and `decision`, and post a check run.
- The check run shows the probability, a baseline for comparison, the threshold, the decision the policy would make, and the top contributing factors in plain language. Its conclusion is always neutral in shadow mode so it never blocks a merge.
- Tenant isolation: every query is scoped by tenant, with a test that tries to read across tenants and fails.

Done when:
- Installing the app on a test organisation backfills a repository and produces check runs on new pull requests within a couple of minutes.
- Replaying the same webhook twice produces one decision, not two.
- All GitHub calls go through the connector module and are mocked in tests.

### Milestone 5: Policy engine and reviewer routing

Build:
- A policy file read from the customer's default branch, for example `.ephorate/policy.yml`, with: the risk threshold, paths that always require a human, paths that never count, and required checks that must pass first.
- Schema validation with clear error messages posted in the check run when the file is invalid. An invalid or missing policy means every change is treated as above threshold.
- Reviewer suggestion for above-threshold changes, ranked by familiarity with the touched files and recent review load.
- Optional Slack notification to the suggested reviewer. **HUMAN:** create the Slack app and supply credentials.
- Every policy evaluation records the hash of the policy file in `decision`.

Done when:
- Changing the threshold in the policy file changes decisions on the next pull request, and the audit log shows the old and new policy hashes.
- A path listed as always requiring a human is never marked below threshold, proven by a test.

### Milestone 6: Outcome tracking and dashboard

Build:
- Connectors for PagerDuty and Datadog that import incidents on a schedule. **HUMAN:** supply read-only API keys for a test account.
- Continuous linking of new incidents, reverts and hotfixes to merged changes.
- A scheduled model refresh that retrains and recalibrates, versions the model, and only promotes a new version if it is at least as well calibrated as the current one on recent data.
- Dashboard pages:
  - escape rate: linked incidents among changes scored below threshold versus above, over time;
  - calibration: predicted versus observed rates;
  - throughput: share of changes below threshold, and estimated review hours that represents;
  - decision log: searchable, with the stored feature values for each decision;
  - what-if: how the numbers would change at a different threshold.
- Sign-in through GitHub, limited to members of the installed organisation.

Done when:
- An incident imported from the test account is linked to a change and appears in the escape-rate view.
- A model refresh that is worse than the current version is rejected, proven by a test.
- Every number on the dashboard can be traced to rows in the database.

### Milestone 7: Deployment

Prepare everything; a person runs the first production deploy.

Build:
- Dockerfiles for the API, the worker and the dashboard.
- Terraform for: a VPC with private subnets; container hosting for API and workers (ECS on Fargate is the default suggestion); managed PostgreSQL with encryption and automated backups; a load balancer with TLS; a secrets store; log and metric collection; least-privilege IAM roles.
- ClickHouse and Temporal: use the managed cloud offerings by default to avoid operating them. Record the choice and cost estimate in `notes/DECISIONS.md` and ask before provisioning.
- Two environments, staging and production, from the same Terraform with different variables.
- GitHub Actions pipeline: on merge to main, build images, run migrations against staging, deploy to staging, run smoke tests. Production deploy is a manual approval step.
- Database migrations that are backward compatible for one release, so a rollback is safe.
- `notes/RUNBOOK.md`: how to deploy, roll back, rotate the GitHub App key, restore the database, and what each alert means.
- Alerts for: webhook failures, scoring latency, workflow backlog, failed model refresh, and error rate.

**HUMAN:** provide the AWS account and a deploy role; approve the cost estimate; register the domain and certificates; create the production GitHub App; run and approve the first production deploy.

Done when:
- A fresh staging environment can be created from an empty AWS account with `terraform apply` plus the documented manual steps.
- A deploy followed by a rollback leaves the service healthy.
- Smoke tests in staging cover: webhook received, pull request scored, check run posted, dashboard loads.

### Website and README

The public website is a single static file, `docs/index.html`, published with GitHub Pages (repository Settings, Pages, deploy from the `main` branch, `/docs` folder). `docs/.nojekyll` keeps GitHub from processing it. Engineering notes live in `notes/`, never in `docs/`, so they are not published.

Keep the website and `README.md` truthful as the project moves:
- Update the "Where it stands" list on the website and the Status table in the README at the end of each milestone.
- Never add customer logos, testimonials, usage numbers or benchmark results that are not real and verifiable. Example values must stay labelled as examples.
- Replace the placeholders `YOUR-USERNAME` and `hello@example.com` once the human owner supplies the real values.

## 7. Security and privacy requirements

These apply from Milestone 4 onward and are part of every acceptance check.

- Source code is processed in memory for feature extraction and not stored. Store features, file paths and commit identifiers. If storing code ever becomes necessary, stop and ask.
- If LLM tagging is enabled for a tenant, record that fact in the tenant's settings and send only the diff, never the wider repository. It is off by default.
- Encrypt data at rest and in transit. GitHub App private keys and customer API keys live only in the secrets store.
- All tenant data access goes through one scoped data-access layer.
- A tenant can be fully deleted by one documented procedure.
- Dependencies are scanned in CI.

## 8. Testing strategy

- Unit tests for linking, signals, policy evaluation and calibration, using synthetic repositories created inside the tests.
- Integration tests with mocked connectors for the full scoring flow.
- A backtest regression test: on a small pinned public repository, the headline metrics stay within a tolerance of recorded values, so a change that quietly breaks the model is caught.
- Contract tests for webhook payloads using recorded examples from a test organisation, with any private content removed.

## 9. What to report back

At the end of each milestone, write a short summary for the human owner:
- what was built and how to run it;
- the acceptance criteria and the evidence for each;
- decisions made where the plan left room, with reasons;
- anything that did not work as the plan assumed;
- what is needed from a person before the next milestone.

If something cannot be verified, say so. A milestone reported as done with an untested path is worse than one reported as incomplete.

## 10. Open decisions for the human owner

- Which public repositories to use for the first backtest, if the agent's proposal is not acceptable.
- Whether design-partner incident data is available before Milestone 3.
- LLM provider for the optional tagging feature.
- Managed versus self-hosted ClickHouse and Temporal, after seeing the cost estimate.
- Go or no-go after the backtest report.
- When, if ever, to allow the service to approve or merge changes. This plan ships shadow mode only.
