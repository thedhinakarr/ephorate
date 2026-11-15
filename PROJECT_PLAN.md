# Ephorate: review capacity simulator plan

Replanned 2026-11-15. This supersedes the incident-risk direction in `archive/2026-11-incident-risk/`. Read `AGENTS.md` first. This session produces planning documents and a landing-page revision only; new M0 needs a separate owner assignment.

## 1. Goal and credibility gate

**Find out where code review will break as your agents write more code, and what would fix it.**

Build a Python CLI and GitHub Action that read one repository's GitHub history, measure area-level demand and shared review capacity, backtest forecasts, and simulate interventions. Outputs are local/CI HTML and JSON artifacts plus optional ownership suggestions. There is no hosted service.

The former direction needed unavailable customer incident data and competed with products identified in owner-supplied research. These observations explain the pivot; an exhaustive competitive gap has not been independently established. The new model's usefulness is unproven. M3 must test it before scenarios are built.

The supplied Chen/Stratton paper motivates the problem, not this product's accuracy. Its submission-to-merge increase is 56.1%; waiting/active-review effects use a commented subset and cannot be added to reconstruct the overall effect. Its firm/repository familiarity measure differs from the area-level adaptation below. The owner's 48%-to-21% coverage case is unsourced here; never use those figures as fitted parameters or verified marketing evidence.

## 2. Architecture and scope

```text
GitHub REST metadata + CODEOWNERS configuration
              |
       resumable collector
              |
    local SQLite metadata store
              |
   areas + as-of measurements
              |
   observed-throughput simulation
              |
  chronological backtest / owner gate
              |
  scenarios + system interventions
              |
  self-contained HTML + JSON + suggested ownership diff
```

| Choice | Decision |
|---|---|
| Runtime | Python; stdlib argparse and sqlite3 in M0 |
| Package | One installable `src/ephorate/` package and `ephorate` command |
| State | SQLite: transactional updates/checkpoints without a server |
| Simulation | Small discrete-event engine using a priority queue; no closed-form queue formula as the forecast model |
| Configuration | TOML; built-in tomllib; one versioned agent-identity rules file |
| Reports | Self-contained HTML and versioned JSON; no remote report assets or telemetry |
| Delivery | Local CLI, then GitHub Action with read permissions and artifact upload |

No FastAPI, PostgreSQL, ClickHouse, Temporal, Terraform, AWS, incident connector, LLM, PR check writer, auto-merge, policy enforcement, or hosted dashboard. Adding hosting or an LLM requires an owner decision. Preserve the existing marketing design; it is separate from the future report.

Planned paths are created only when their milestones need them:

```text
AGENTS.md, PROJECT_PLAN.md, README.md, index.html
src/ephorate/             CLI, store, client, collector, measures, model, reports
tests/                   unit/contract tests; sanitized metadata fixtures
docs/                    decisions, dictionary, backtest report
agent_instruction/       index, log, handoffs, actual implementation/results
action.yml               introduced in M5
archive/2026-11-incident-risk/  historical plan, handoff and pitch
```

The public personal repository is `thedhinakarr/ephorate`. `ephorate.dev` is the intended purchase domain, not a deployed endpoint. The root plan is authoritative; the nested `ephorate/` starter and ZIP remain historical references.

## 3. Data and measurement contract

[DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) defines timestamps, cohorts, formulas, provenance, and missing-value behavior. Use its words consistently in code and reports. All time is UTC. Default reporting covers the previous 12 calendar months ending at an explicit exclusive cutoff. Collect 90 additional warm-up days for the default qualification lookback, plus PRs already open at the reporting start. Warm-up does not enter headline totals.

- **Area:** a named path set. Each changed file has one winning area: explicit configured rule, CODEOWNERS last match, then top-level directory/root fallback. A PR's changed-file shares across areas sum to one; touching multiple areas does not multiply its workload.
- **Qualified reviewer:** at event time, a non-bot person with the configured count of distinct qualifying PRs in the preceding lookback. Defaults: 90 days and one PR. Qualification comes from merged authorship or submitted reviews touching the area, strictly before the measured event. CODEOWNERS alone does not qualify anyone.
- **Familiarity:** review-event familiarity uses prior qualification and fractional area weights. Its random baseline assigns that reviewer uniformly to non-self-authored PRs opened in the same repository/month. This is an area-level adaptation, not the paper's firm-wide baseline. Same-month future candidates are for descriptive measurement only, never predictive features.
- **Waiting:** opening, or first ready-for-review for an initially draft PR, to first eligible non-author human review/comment. Bots and unpublished pending reviews do not count. No response means censored, not zero.
- **Active review time:** elapsed first-human-interaction-to-merge latency. It includes rework, idle time, and merge delay; it is not measured person-hours.
- **Human review coverage:** share of merged PRs with a submitted formal human review before merge. Report comment-only engagement coverage separately. Missing records do not prove nobody inspected code.
- **Effective review capacity:** observed response throughput under historical conditions, with one reviewer budget shared across areas. It is not independently measured maximum ability or attention.
- **Utilization/review ceiling:** arrivals divided by modeled capacity, and the arrival rate where modeled utilization reaches one. Show gross and human-routed demand separately. Unbounded growth assumes persistent overload without bypass, abandonment, or adaptation; finite simulations report their actual horizon.
- **Agent-authored:** detectable coding-agent account/trailer evidence. Dependency bots, no detected agent evidence, and incomplete/unknown attribution remain separate. One configurable identity file controls recognition. Dependency bots are excluded from headline human/agent comparisons but remain background demand when they use shared review capacity.

The dictionary covers zero denominators, deleted actors, draft/reopen events, pending/dismissed reviews, partial collections, path overlap, multi-area accounting, seniority mappings, and historical snapshot limits. Default person detail is hidden; the single future `--people hide|show` option applies across all outputs.

## 4. Collector and privacy boundary

Use GitHub REST with `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2026-03-10`, and environment-only authentication. All GitHub operations are `GET`, through one mockable client. Never store credentials, raw response caches, PR titles/bodies, review/comment text, commit messages, patches, or diff hunks.

Required endpoints cover repository metadata; updated-order PR listing and detail; issue timeline; submitted reviews; inline/conversation comments; changed paths; and PR commits for attribution. The endpoint/retained-field map is in the dictionary. Parse recognized co-author trailers transiently and retain classification/rule provenance, not message text or emails.

REST metadata responses include incidental snippets/free text and offer no field-projection switch. Allowlist metadata immediately in memory; discard everything else before persistence, logs, error reporting, fixtures, or reports. Never request raw/blob/diff/patch/archive payloads.

**Owner-approved CODEOWNERS exception:** inspect a pinned commit's tree metadata for the first existing CODEOWNERS path in `.github/`, root, then `docs/`. Validate that selected entry as a regular file; reject symlinks/submodules and files at or above 3 MB. An unsafe/unusable selected path triggers non-CODEOWNERS area fallbacks, not a lower-precedence CODEOWNERS file. Fetch only the verified path through the Contents API, without following download URLs. Retain parsed rules/provenance. Current ownership is not historical qualification; freeze the area taxonomy for evaluation and disclose final-diff approximations.

Collection must paginate, deduplicate stable IDs, checkpoint sanitized state transactionally, honor `Retry-After`/rate-reset, retry transient failures with bounded backoff, and emit visible partial status when interrupted. Validate pagination and redirect destinations before forwarding credentials. Never advance a complete-run watermark while child collections are incomplete.

PR listing has no `since`: use updated-descending discovery with overlap and conditional requests, restarting discovery safely after interruption rather than trusting old page positions. Incremental means new **and changed** records, not zero requests. Use ETags to avoid unchanged child downloads. Run a full reconciliation every seven successful daily incremental runs to address missed edits/deletions, and record that cost.

Respect the 3,000-files and 250-commits PR endpoint caps. Mark oversized PRs incomplete; never label missing attribution human or derive exact area weights from partial files. Current/final PR files are not historical opening-time paths. Initial-queue and warm-up completeness are separate flags.

The workflow token is repository-scoped and has a limited quota; an initial year may need several resumable CI runs. Own-repository workflows request only `contents: read` and `pull-requests: read`. Another private repository requires separately authorized read credentials. Data stays on the operator's machine/runner and in authorized GitHub artifacts, not an Ephorate backend. No literal promise that a local CLI's data remains inside a GitHub account.

## 5. Model and interventions

Use a discrete-event model of **first human response and elapsed completion**, not inferred labor time. Explain the model on one page in each report:

1. Each PR is one global job with fractional area attribution, origin time, and actor class. Preserve open jobs at the train/test boundary.
2. Bootstrap contiguous observed training-week blocks for arrivals and time-of-week response opportunities. An opportunity is one unique first-human-response token. If responders tie, assign the token to one of them using fixed-seed uniform selection; retain tie provenance. Never let fractional descriptive allocations release multiple jobs. Each person's weekly opportunity budget is shared across all areas. This is an observed-activity proxy for availability.
3. Freeze the qualification snapshot and area taxonomy at forecast cutoff. At a review opportunity, choose the oldest queued PR touching an area for which that reviewer is qualified. This represents initial response, not comprehensive review sufficiency over every path; disclose cross-area limitations.
4. While a job awaits response, model separate competing exits for merge without engagement and closure without merge. Estimate empirical age-dependent exit hazards from training risk sets, conditioned on pre-arrival pressure; censor still-open observations rather than treating them as exits. A terminal exit removes a queued job and records its outcome. A formal-review label alone never bypasses the first-response queue: comment-only engagement still consumes an opportunity.
5. After a response, use empirical competing merge/closed-unmerged timing from training, retaining right-censored jobs. Post-response latency does not monopolize the reviewer. Fit formal-review probability by pre-arrival pressure and engagement/exit route. Reviews outside an open-ready interval can count toward formal coverage without ending this waiting measure: preserve that separate participation flag for carry-in jobs and model its observed frequency for new jobs, without creating response tokens. Thus formal coverage, first response, and terminal exits remain distinct. Use supported area distributions or a disclosed repository fallback. Pressure uses backlog/capacity knowable before arrival. These relationships are observational, not proof that pressure causes bypass; never import the unsourced case-study percentages.
6. Report coverage, all arrivals, queue growth, terminal exits and unfinished work together. Add a sensitivity run holding bypass hazards and formal-review probabilities at their baseline-pressure values so reduced waits caused by bypass are visible. Exempted or deferred work never disappears from demand accounting.
7. Use fixed seeds and repeated draws; report fitted window, draw count, model/config versions, support, assumptions, and held-out errors next to each supported forecast. Abstain for insufficient/out-of-support data.

Before M3 fitting, its handoff must freeze training-only pressure/age bins, support and fallback rules, simulation horizon, seeds and aggregation. The dictionary defines M2's descriptive first-response throughput; M3 fits the empirical opportunity and exit processes from it and lifecycle records. No test-quarter tuning. Failure to identify a useful model is a failed credibility gate, not permission to invent availability or exclude poorly predicted areas.

M4 configuration represents `qualify_reviewer`, `exempt_class`, `agent_wip_limit`, `agent_size_limit`, and `reallocate_review_capacity`. Eligibility alone adds no capacity. A person absent from response history requires explicit assumed capacity and an unsupported-new-person warning. The first size-limit version **defers** oversized work rather than pretending it is split; show that upstream backlog. WIP limits also preserve deferred demand. Exemptions show reduced coverage and imply no safety decision. Reallocation conserves budgets and shows cross-area spillovers.

Rank system interventions by waiting/backlog effect only within stated coverage/assumption constraints. Show uncertainty and coverage changes alongside effects. Named candidates are opt-in and unranked; no person-performance score or leaderboard.

## 6. Milestones

### M0 - Skeleton

Build only an installable CLI package, safe local SQLite initialization, tests, lint/type checks, wheel build, and CI. Follow the [new M0 handoff](agent_instruction/what-has-to-be-done/2026-11-15-milestone-0-review-capacity.md). No collector, simulation, report, server, container, or Action distribution yet.

Acceptance: locked install/lint/test/build pass from a clean clone; install the built wheel separately and invoke its CLI outside the checkout; help/version create no application stores, output or configuration; SQLite initialization is repeatable and rejects foreign/corrupt/unsupported stores without modification; CI needs no token or services. README shows actual commands. Report evidence to the owner before M1 assignment.

### M1 - Collect history

Implement one-repository collection for the explicit reporting/warm-up window and initial queue. Store only normalized metadata, observed cutoffs/SHAs, attribution rules, completeness, and transactional checkpoint/ETag state. Add only the HTTP client actually required, after current documentation checks.

Acceptance:
- Collect a reporting year for initial public target `pytest-dev/pytest`, retaining warm-up and initial-queue evidence or declaring them incomplete. If its current volume/API behavior is unsuitable, document evidence before proposing a replacement.
- An interrupted/resumed fixture run produces the same normalized rows as uninterrupted collection, without duplicate or missing children.
- A second run fetches new/changed records and conditionally validates unchanged data; no blanket year-long re-download.
- Sanitized public fixtures and synthetic edge cases cover pagination, quotas, retries, redaction, pending reviews, endpoint caps, denied CODEOWNERS paths/symlinks, and partial status. Unit tests never contact GitHub.
- Live validation records dates, counts, requests, quota/partial status and resume evidence, never raw responses. Report to the owner.

### M2 - Map and measure

Implement the dictionary: area rules, temporal qualification, familiarity/adapted baseline, waiting/elapsed latency, review-load concentration, formal/engagement coverage, observed response throughput, detectable authorship, and optional supplied seniority versus observed repository tenure.

Acceptance:
- All defined measures exist for the target with denominators, lineage, completeness, and no fabricated values.
- Hand-check 30 sampled PRs covering drafts, human/agent/dependency-bot classes, multi-area changes, comment-only interactions, and censored/unreviewed cases. Record absent strata and expected/computed waiting, coverage and familiarity. No undisclosed LLM ground truth.
- Tests prove future events cannot confer earlier qualification; area/reviewer accounting conserves totals; bot/author/pending events cannot falsely end waiting; missing responses remain censored; hiding people suppresses identities across outputs.
- Explicitly report final-diff/current-ownership approximation and incomplete-history limits. Report to the owner.

### M3 - Capacity model and backtest

Implement discrete-event simulation with bootstrap-arrival forecasting as the primary gate. Fit on reporting months 1-9 and predict months 10-12, preserving the boundary queue and censoring. Truncate all training responses, merges, lifecycle/exit events and qualifications at the training cutoff; a training-origin PR resolved during the test period is censored during fitting. Replay using realized test arrivals is a separately labeled diagnostic, never the primary forecast result. The naive baseline predicts each area's next-quarter mean waiting as its preceding-quarter mean, using the same cohort definition and a disclosed repository fallback for zero prior support.

The primary waiting estimand is mean elapsed waiting among first responses observed by the quarter-end cutoff, grouped by the PR's arrival week and fractional area. Apply the same quarter-relative observation horizon to the preceding-quarter baseline and simulated quarter. This is conditional on an observed response, not an uncensored population mean; report response, unengaged-exit and unresolved shares alongside it. Carry-in jobs affect capacity/backlog but are reported separately from new-arrival waiting. Freeze this cohort, censoring treatment and bin eligibility before fitting. Forecast and actual aggregates share week/area bins, not synthetic/real PR identities; a bin lacking simulated response support is unavailable, never silently omitted from the coverage report.

Evaluate at least three public repositories. Candidate pool: `pytest-dev/pytest`, `django/django`, `astral-sh/ruff`, `pallets/flask`, `fastapi/fastapi`, `pandas-dev/pandas`. Select three using measured **training-period** PR volume and detectable agent-share spread; repository names do not establish usage. If the pool lacks meaningful spread, report this and propose expansion rather than falsely passing that criterion.

Acceptance:
- `docs/BACKTEST_REPORT.md` records each repository/window, context, model, assumptions, support, missingness and reproducibility inputs.
- Compare weekly per-area mean waiting against the baseline on the same eligible test bins, weighted by actual observed-response PR equivalents. Report weighted MAE in hours per repository, per-area errors, median/p90 diagnostics, unresolved/censored shares, and a paired calendar-week block-bootstrap interval for the MAE difference. Keep counts and unavailable bins visible so censoring cannot improve appearances.
- Separately report backlog error and formal-coverage error/calibration, with prior-quarter constant baselines. Do not accept short waits obtained by hiding bypass or unfinished PRs.
- Freeze support/abstention rules before test inspection and report every area's outcome. Fixed seeds/data/config versions reproduce results within a recorded tolerance.
- Honest failure is valid: if waiting does not beat the naive baseline, or coverage/backlog accuracy is inadequate, say so and propose changes. No guaranteed positive result.

**Stop after M3 and report to the owner. Do not begin M4 without explicit go-ahead**, even after positive results. Evaluation is not approval to publish named public examples on the website.

### M4 - Scenarios and fixes

Add agent-arrival multipliers and the intervention types in section 5. Keep human, dependency-bot and unknown background demand explicit. Every scenario carries horizon, baseline comparison, held-out errors, uncertainty, coverage, deferred work and unsupported assumptions.

Acceptance: each intervention is a small validated TOML entry. A fixed-seed synthetic test shows that a newly qualified reviewer **with spare capacity** reduces waiting in an overloaded area. Other tests prove qualification cannot duplicate capacity, reallocation conserves budgets, caps preserve deferred demand, and exemptions visibly change coverage. Rank interventions, never individuals. Report to the owner.

### M5 - Report and GitHub Action

Create a self-contained HTML report, versioned JSON, and separate suggested CODEOWNERS diff when needed. Reports make no external requests. `--people hide|show` defaults to `hide` and governs HTML, JSON, suggestions, logs and filenames; hidden-person mode suppresses named suggestions.

Provide an Action usable in a few lines, with read-only GitHub permissions and allowlisted artifact upload. Document resumable sanitized-store caching, retention and access. Never upload a workspace glob, secrets, or raw responses. Partial collections remain visibly partial.

Acceptance: this repo's CI runs the Action against a chosen public target and uploads HTML/JSON; a rerun resumes/reuses metadata; offline browser QA checks layout/accessibility; tests verify no external report requests, no identities in hide mode, traceable HTML/JSON agreement, and suggestion artifacts that leave CODEOWNERS unchanged. Report to the owner.

### M6 - Public examples

Prepare proposed targets and masked reports. **The owner approves the repository list before website publication.** Describe systems, not people. Remove/mask names, handles, named suggestions, identity-bearing URLs, filenames and metadata. Show model error/support prominently.

Acceptance: approval recorded; masking independently checked; every published example links its window, definition/model versions, errors and limits; website links resolve and artifacts work offline. Public source data does not waive this review. Report to the owner.

## 7. Validation and risk register

Unit/contract tests cover parsing, SQLite safety, time ordering, qualification, conservation, partial data, censoring, simulation determinism and hidden identities. Use sanitized public metadata and small synthetic cases. Live runs are separately invoked validation, never unit-test dependencies. Every milestone records commands, exit statuses, counts and missing checks; no invented passes or completion records before work exists.

| Risk | Response |
|---|---|
| Incumbents hold data and could add forecasting | Move quickly with inspectable methods; do not claim uniqueness or an open-source license before verification/selection |
| Holidays, reorganizations, departures and irregular behavior break forecasts | Held-out evaluation, uncertainty/support limits, and invalidation after structural changes |
| Open-source patterns do not transfer to companies | Describe repository context; do not generalize public results to companies |
| Agent detection undercounts usage | Display rules, unknowns and undercount caveats with every share |
| API quotas, pagination, edits and historical caps | Transactional incremental checkpoints, reconciliation, visible partial states and realistic multi-run backfills |
| Metadata cannot identify true labor capacity | Effective-throughput language, conserved budgets, disclosed assumptions; no staffing/performance claims |
| Pressure and coverage are confounded | Observational wording, separate coverage validation and fixed-coverage sensitivity |
| Current paths/ownership leak future state | Frozen taxonomy, as-of qualification, observation provenance, disclosed historical approximation |
| Sparse areas | Abstain instead of fabricated forecasts; expose support and fallback scope |
| Public examples expose or grade people | Default hiding, no person rankings, owner-approved publication and masking checks |

## 8. Owner decisions and sources

Already decided: Ephorate name, intended `ephorate.dev` domain, personal/public GitHub, CODEOWNERS-only content exception, and retaining `jellyfish.pdf` publicly. Pending at their gates: new M0 assignment, M3 continuation, license, public-example list, and domain/hosting purchases. No history rewrite or PDF removal is authorized.

Current source checks (2026-11-15):

- Supplied study: repository `jellyfish.pdf`, 9 November version. [Authors' copy](https://fion.ac/jellyfish.pdf) now has a 14 November version; preserve attribution/version differences.
- [REST versioning](https://docs.github.com/en/rest/about-the-rest-api/api-versions), [PR endpoints/caps](https://docs.github.com/en/rest/pulls/pulls), [review comments](https://docs.github.com/en/rest/pulls/comments), [timeline](https://docs.github.com/en/rest/issues/timeline).
- [CODEOWNERS precedence/size](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), [Contents behavior](https://docs.github.com/en/rest/repos/contents).
- [REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), [workflow-token scope](https://docs.github.com/en/actions/concepts/security/github_token).

These establish interfaces and research definitions, not product efficacy. No new collector, capacity model, or end-to-end Action has run in this replanning session.
