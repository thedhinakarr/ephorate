# Ephorate data dictionary

Status: planning contract for the review capacity simulator; nothing described here is implemented. Updated 2026-11-15. Defaults below apply unless an explicit configuration override is recorded with the run.

## Time, population, and provenance

- Store timestamps as timezone-aware UTC instants; display UTC and elapsed seconds/days. Do not infer local working hours, holidays, or time zones from account activity.
- Freeze `as_of` when a collection run starts. The default reporting interval is `[as_of minus 12 calendar months, as_of)`; calendar subtraction preserves UTC day/time, clamping an invalid day to the target month's last day. Report the exact boundaries.
- Collect a further 90 days before the reporting interval for qualification warmup. Also collect PRs already open at the reporting start, including older PRs that close or merge during the interval; they contribute initial backlog rather than new arrivals.
- Default qualification lookback is 90 elapsed days, and minimum evidence is one distinct qualifying PR. Record overrides. Weekly rates use seven-day UTC bins anchored at reporting start; normalize partial bins by their actual duration. Calendar-month baselines use UTC month boundaries.
- Different measures have different cohorts: arrivals by waiting origin, reviews by submission time, and coverage by merge time. Every aggregate exposes its cohort, numerator, denominator, exclusions, and whether observations are censored.
- Persist stable repository/PR/event/actor IDs, paths, timestamps, counts, collection `observed_at`, API version, base/head SHAs, configuration hash, classifier version, area-map hash/ref, and per-resource completeness. Log identifiers/counts only.
- Each run records reporting/warmup boundaries, successful synchronization watermark, pending work, endpoint/page checkpoints, ETags, request counts, and `complete` or `partial`. A successful HTTP request is not proof of a complete repository window.
- Historical snapshots are reconstructed from available metadata, not a perfect event archive. Deleted comments, inaccessible actors, rewritten commits, and final PR diffs can leave irrecoverable gaps. Attach the affected limitation to derived metrics.

## Actors and authorship

| Field | Definition |
|---|---|
| Actor identity | GitHub numeric user ID is the stable key; login is a changeable display label. A missing/deleted identity is unresolved, not automatically human. |
| `author_class` | `human`, `coding_agent`, `dependency_bot`, `other_bot`, or `unknown`. A `Bot` account type alone does not identify a coding agent. |
| Agent detection | A configured coding-agent account match or recognized AI co-author trailer in a PR commit. Persist the matching rule ID and commit SHA, not the commit message or email. Detection is attribution evidence, not proof of all AI use. |
| Classification precedence | Explicit dependency-bot matches remain `dependency_bot`; then coding-agent account/trailer matches; then other known bots; then resolved human accounts with complete attribution evidence; otherwise `unknown`. |
| Headline population | Human and detected coding-agent PRs. Exclude dependency/other bots; show unknown and excluded counts separately. Never convert incomplete commit inspection into evidence of human authorship. |
| Human participation | A resolved human account, excluding configured bots/agents and the PR author. Human contributors to agent-authored PRs remain eligible reviewers. |

Use one versioned configuration file for account/trailer rules. Commit messages are parsed transiently for the documented [co-author trailer format][coauthors] and immediately discarded. An agent share is always labeled **detectable agent attribution**, with unknown coverage beside it.

## Areas and qualification

- An area is a named path set. Every changed file has exactly one winning area: first matching explicit configuration rule; otherwise last matching CODEOWNERS entry; otherwise its top-level directory, with `root` for root-level files. Namespace generated names (`codeowners:<rule-line>`, `dir:<name>`, `root`) and hash the complete map.
- Match paths case-sensitively. CODEOWNERS rules follow GitHub's supported syntax, not unrestricted gitignore syntax. Preserve the selected file's rule order; unsupported/invalid rules are reported and excluded, never silently given invented semantics.
- A rename uses its current `filename` for area assignment; retain `previous_filename` only as provenance. A deleted file retains the path returned by GitHub. Do not fetch files to decide their area.
- For complete changed-file set `F`, PR weight in area `a` is `count(files assigned to a) / count(F)`. Weights sum to one. An empty or incomplete file set yields unknown area weights, not zero-sized work or renormalized partial coverage.
- A PR qualifies a person for each area it touches after either (a) their authored PR merges, or (b) they submit a formal review on that PR. An author's own review does not qualify them. CODEOWNERS ownership alone never establishes qualification.
- At event time `t`, count distinct PR IDs with qualifying evidence in `[t - lookback, t)`. Union authored/reviewed evidence so the same PR counts once; repeated review rounds do not increase the count. Require the configured minimum count. The event being measured cannot qualify itself, including when timestamps tie.
- Store the qualifying evidence IDs and timestamps needed to reproduce membership. Missing actor/path/evidence completeness makes the affected membership unknown; it does not prove unfamiliarity.
- Freeze the area taxonomy before model evaluation. Current CODEOWNERS is a current map, not historical ownership; historical PR file listings usually reflect the final/current diff. Label this area-assignment approximation and never describe it as exact opening-time reconstruction.

## Review events and elapsed times

| Term | Exact meaning |
|---|---|
| Formal review | A submitted GitHub review with `submitted_at`; `PENDING` reviews are excluded. APPROVED, CHANGES_REQUESTED, COMMENTED, and later-DISMISSED submitted reviews all represent activity, not necessarily approval. |
| Visible inline comment | Nonpending comment associated with a submitted review; event time is `max(created_at, parent_review.submitted_at)`. This is a visibility approximation. An unresolved parent makes its timing unknown. |
| Conversation comment | An issue comment on the PR, at `created_at`; its text is never retained. It is engagement, not a formal review. |
| Waiting origin | `created_at` for a PR opened ready; first `ready_for_review` event for an initially draft PR. Preserve draft/ready transitions; if initial state or first readiness cannot be established, mark origin unknown. |
| First human engagement | Earliest eligible nonauthor human submitted review, visible inline comment, or conversation comment at/after waiting origin, during an open-ready interval and before merge/as_of. Deduplicate event IDs and retain the winning evidence ID. |
| Waiting time | First human engagement minus waiting origin. Later returns to draft are exposed as intervals but are not subtracted from this elapsed measure. |
| Active review time | Merge time minus first human engagement, only when both are known and engagement precedes merge. This is elapsed post-response time, not measured reviewer labor or a queue service duration. |
| Submission-to-merge time | Merge time minus `created_at`, shown separately from ready-to-merge time. It is not approval time. |
| Unanswered PR | End observation at `as_of`, merge, or final closure without merge, whichever applies first. Distinguish right-censoring from competing terminal exits `merged_without_engagement` and `closed_without_engagement`. Never encode no response as zero. Drafts never ready are not ready arrivals. |

A still-open PR with engagement has a censored active-review interval. A closed-unmerged PR is a separate exit outcome, not a merged completion. Negative intervals and impossible event order are quarantined with counts/reasons; do not silently clamp them. Timestamp ties at merge cannot establish strictly-before-merge participation. [Reviews][reviews], [review comments][review-comments], and [timeline events][timeline] provide the underlying records.

For close/reopen and draft/ready cycles, retain the original waiting origin and first eligible engagement across the PR's lifetime; do not count a reopened PR as a second arrival. Only open-ready intervals can end waiting. Before first engagement, closing or returning to draft removes the PR from the ready backlog; reopening/readying it restores that same unanswered job. Elapsed waiting includes these interruptions and reports their durations separately. An intermediate closure followed by a known reopen is not a terminal censoring event. An already-engaged reopened PR does not re-enter the first-response queue. Missing lifecycle events make affected intervals unknown rather than guessed. Formal-review coverage still counts any eligible submitted review before merge, independently of the first-response interval filter.

## Coverage, familiarity, and distribution

- **Formal human review coverage:** among headline PRs merged within the reporting interval, the fraction with at least one eligible submitted human review strictly before merge. Count each PR once. Comments alone do not satisfy this measure.
- **Human engagement coverage:** the analogous fraction with eligible formal review, inline comment, or conversation comment before merge. Report separately; never relabel it formal review coverage.
- For each coverage measure show known eligible count, positive count, unknown count, and excluded count. Report the fraction over known outcomes and its known-outcome coverage; incomplete observations must not silently shrink the denominator or imply a negative.
- **Familiarity share:** for each eligible formal review event, sum the reviewed PR's area weights for which that reviewer was qualified strictly before submission; average these event scores. Repeated submitted reviews are separate events for this descriptive measure. Show unknown-event exclusions and qualifying-history completeness.
- **Random-assignment baseline:** keep the reviewer's identity and review timestamp fixed. Uniformly choose from headline PRs opened by someone else in the same repository and UTC calendar month as the reviewed PR. For each candidate, sum its area weights qualified for this reviewer at the fixed review time; average over candidates, then over eligible review events. An empty or incomplete candidate pool yields unavailable/partial baseline, not zero.
- This is an **area-level, single-repository adaptation**, not a replication of the paper's firm/repository statistic. A monthly candidate pool can include PRs opened after the review: it is retrospective descriptive context and must never enter prediction features or training-time qualification.
- **Review distribution:** report area-level review volumes, share of work concentrated in the busiest review capacity pools, and the number of active/qualified reviewers. A person's repeated reviews of one PR count once for capacity allocation; formal review-event totals remain a separately named measure. No individual ranking or speed scores.

## Capacity and simulation quantities

| Term | Meaning and required limit |
|---|---|
| Area arrivals | Sum PR area weights whose waiting origins fall in a bin; split human/detected-agent arrivals, with excluded/unknown volumes disclosed. |
| Backlog | Outstanding ready PR equivalents awaiting their first eligible human engagement at time `t`, including known carry-in PRs. Closed/merged exits leave the queue; merges without an eligible first response are recorded separately from formal coverage. |
| Effective observed capacity | M2 descriptive proxy: one PR-equivalent per distinct first-human-engagement event, divided among tied responders and attributed fractionally by PR area weights. Divide bin totals by observed weeks. Count only allocations where the responder was qualified for that area before the event; disclose unqualified/unknown allocations separately. One shared person's total cannot be duplicated across areas. This is observed throughput, not maximum capacity. |
| Capacity estimator contract | Repeated review/comment events on the same PR add no first-response units. Keep formal-review volumes separately named. Area allocations for a person sum to at most that person's total opportunity budget, including background bot/unknown-PR demand. M3 fits opportunity distributions using this work unit and the cutoff qualification snapshot; its handoff fixes support, temporal sampling and exit-model details before fitting. |
| Utilization | Comparable area demand divided by allocated effective capacity. Zero observed capacity gives unavailable utilization, or an explicit overload/no-observed-capacity state for positive arrivals; never silently divide by zero. |
| Review ceiling | Arrival rate at which demand meets the fitted area's effective capacity under stated shared-reviewer allocation assumptions. Not a measured immutable personal/team limit. |
| Review duration/availability | Latent simulation assumptions fitted from observable response/completion patterns. GitHub elapsed times do not measure uninterrupted service time, working hours, or free reviewer availability. |
| Predicted coverage | Scenario estimate of formal human review coverage among simulated merges, always paired with waiting/backlog and engagement coverage. Comment-only engagement uses capacity despite lacking formal review. Only a separately modeled unengaged terminal exit bypasses the first-response queue. Show unengaged merges, closed-unmerged exits and unfinished counts; pressure associations are not causal laws. |

Utilization near/above one signals instability only under the model's stationary, no-bypass assumptions. Finite windows, changing capacity, and skipped review prevent a universal claim that observed queues grow without limit. Forecasts carry the comparable time-ordered backtest error, baseline error, uncertainty interval, training support, and model/configuration versions. Unsupported areas/scenarios are labeled insufficient evidence or out of support; do not invent forecast values or suppress error beside a forecast.

## People, seniority, and publication

Per-person details are hidden by default and switchable with one report option. When enabled, use them only to explain shared load or name a possible additional reviewer; do not rank people, label anyone slow, or describe performance. Names are masked or removed for public examples about other projects.

Seniority comes only from an optional owner-supplied mapping. Otherwise show **observed tenure in this repository**, measured since the earliest observed qualifying contribution; this is a lower bound limited by the collection window, not employment tenure or seniority. Do not infer a job level from GitHub activity.

## Collection and privacy boundaries

Use GitHub REST API `2026-03-10`, JSON responses, `per_page=100`, and `Link` pagination. Tokens stay in the environment. The following read paths are the collection allowlist; `{r}` means `/repos/{owner}/{repo}`. [API versioning][api-version], [pagination][pagination].

| Metadata | GET path |
|---|---|
| Repository / PR discovery / PR details | `{r}`; `{r}/pulls?state=all&sort=updated&direction=desc`; `{r}/pulls/{number}` |
| Draft/readiness and lifecycle | `{r}/issues/{number}/timeline` |
| Formal reviews / inline comments | `{r}/pulls/{number}/reviews`; `{r}/pulls/{number}/comments` |
| Conversation comments | `{r}/issues/{number}/comments` |
| Paths / commit attribution | `{r}/pulls/{number}/files`; `{r}/pulls/{number}/commits` |
| Approved CODEOWNERS lookup | Git reference/commit/tree metadata to pin and validate the path; `{r}/contents/{allowlisted_CODEOWNERS_path}?ref={commit_sha}` only |

- Metadata responses can contain `body`, `patch`, `diff_hunk`, commit messages, signatures, and emails. Inspect only needed metadata/trailer fields transiently; discard other fields in memory before storage, caching, fixture recording, logging, or error construction. Never persist raw responses or these text fields. Sanitized public fixtures retain only the allowlisted metadata.
- Do not fetch repository file contents, blobs, archives, or diff/patch media types. The owner-approved sole file-content exception is CODEOWNERS. Check `.github/CODEOWNERS`, `CODEOWNERS`, then `docs/CODEOWNERS`; select the first existing path, then require a regular file under 3 MB at an immutable commit reference. If that selected file is unsafe or unusable, report it and use non-CODEOWNERS area fallbacks rather than silently selecting a lower-precedence file. [CODEOWNERS rules][codeowners].
- Validate regular-file mode from Git-tree metadata before the Contents API, which can dereference symlinks. Reject symlink/submodule entries and oversized/truncated lookups; do not follow download URLs. Parse CODEOWNERS into rule metadata and retain path, commit/blob SHA, content hash, and rule order rather than raw file text. [Contents behavior][contents], [Git trees][trees].
- PR file responses stop at 3,000 files; PR commit responses stop at 250 commits. Compare collected counts with PR metadata; mark truncation/inaccessible resources explicitly. An oversized PR can have known bot authorship but unknown file weights or incomplete trailer attribution. [PR endpoints][pulls].
- PR discovery has no `since` parameter. Use updated-order discovery, overlap/deduplication, conditional ETags, and periodic reconciliation. Resume saved child work transactionally; restart unstable discovery pagination from page one after interruption. Advance the successful watermark only after all required child resources complete.
- A second run may validate unchanged resources: incremental does not mean zero repeat requests. Snapshot consistency, deletion detection, and the historical completeness of child edits are not guaranteed. [GitHub REST best practices][best-practices].
- Requests are serial. Respect `Retry-After` and rate-reset headers, use bounded backoff, and checkpoint before a request/time budget expires. Normal quotas are 1,000 requests/hour/repository for Actions `GITHUB_TOKEN`, 5,000/hour for personal authentication, and 60/hour unauthenticated; actual headers take precedence. Twelve-month backfills may span runs. [Rate limits][rate-limits].
- `GITHUB_TOKEN` permissions are scoped to its workflow repository; another private repository needs separately authorized read access. Use only `contents: read` and `pull-requests: read` for collection. Say **runs in your environment with no Ephorate-hosted upload**, not that data never leaves GitHub: local runners receive metadata. [Token scope][token].

[api-version]: https://docs.github.com/en/rest/about-the-rest-api/api-versions
[pulls]: https://docs.github.com/en/rest/pulls/pulls
[timeline]: https://docs.github.com/en/rest/issues/timeline
[reviews]: https://docs.github.com/en/rest/pulls/reviews
[review-comments]: https://docs.github.com/en/rest/pulls/comments
[coauthors]: https://docs.github.com/en/pull-requests/committing-changes-to-your-project/creating-and-editing-commits/creating-a-commit-with-multiple-authors
[codeowners]: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
[contents]: https://docs.github.com/en/rest/repos/contents
[trees]: https://docs.github.com/en/rest/git/trees
[pagination]: https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
[best-practices]: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
[rate-limits]: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
[token]: https://docs.github.com/en/actions/concepts/security/github_token
