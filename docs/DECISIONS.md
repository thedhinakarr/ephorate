# Ephorate decisions

## 2026-11-15 — Review capacity direction

The owner replaced incident-risk scoring with a Python CLI and GitHub Action for measuring and simulating review capacity. The former master plan, M0 handoff and pitch are archived unchanged under `archive/2026-11-incident-risk/`. The downloaded starter remains historical. This assignment ends with planning and the landing-page revision; it does not implement M0.

**SQLite is the local store.** Standard-library `sqlite3` provides transactions, resumable updates and checkpoints without a server. Parquet would add dependencies and update/rewrite handling. M0 creates only a version marker; M1 must specify the metadata schema and explicit schema transition before collection. No ORM, migration framework or infrastructure services are needed for M0.

**One installed Python package, no M0 runtime dependencies.** Use `src/ephorate`, standard-library argument parsing, and the exact toolchain/CI pins in the [M0 handoff](../agent_instruction/what-has-to-be-done/2026-11-15-milestone-0-review-capacity.md). Official release/package metadata was checked on 15 November; installation and runtime compatibility of the new package have not been tested. Implementation must validate the pins instead of silently changing them.

**Read-only GitHub, local state allowed.** The prompt's “only report files” cannot literally support its required local store and resumable collection. The plan explicitly permits Ephorate-owned metadata state and artifact writes while forbidding changes to GitHub. “No data leaves GitHub” is replaced by the accurate boundary: execution on the operator's machine/runner, with no Ephorate backend or third-party analysis upload.

**CODEOWNERS-only content exception, approved by the owner.** The owner resolved the conflict between requiring CODEOWNERS and forbidding all file-content fetching. Fetch only a verified regular CODEOWNERS file at a pinned commit. Retain parsed rules/provenance. REST metadata endpoints incidentally include text/code fields; discard them immediately in memory and never cache raw responses. The [dictionary](DATA_DICTIONARY.md) specifies the endpoint allowlist and completeness limits.

**Effective response capacity, not measured labor.** GitHub exposes event timestamps, not uninterrupted service time or available work hours. Model first-human-response opportunities with a shared per-person budget; treat post-response-to-merge as elapsed latency. Preserve background demand and cross-area spillovers. A newly qualified person adds no throughput without available or explicitly assumed capacity.

**Research adaptations are labeled.** Area-level qualification, formal-review coverage, and first-response measures use the dictionary's precise definitions. They are not exact reproductions of the paper's firm/repository analysis. Current/final path snapshots limit historical reconstruction. The supplied coverage-drop case and competitive-gap claims are unverified context, not evidence or fitted parameters.

**Credibility before scenarios.** Train on the first nine reporting months, test on the last three, and compare with the prior quarter's waiting baseline on at least three repositories. Validate backlog and coverage too. Every forecast shows error and support; M3 ends at an explicit owner gate regardless of its result.

**People hidden by default.** One `--people hide|show` control governs person detail across future outputs. Person detail can explain shared work or identify a possible reviewer; it cannot grade or rank people. Public examples mask identities and need approval of the repository list. Seniority requires a supplied mapping; observed repository tenure is not seniority.

**Paper retained, by explicit owner decision.** The recommendation to replace `jellyfish.pdf` with an author link was presented. The owner chose to keep the PDF public. No PDF removal or history rewrite is authorized. A future software license must not imply ownership or relicensing of the third-party paper.

**Interrupted scaffold recovered outside the repo.** After explicit permission, exactly 19 agent-created uncommitted scaffold files were moved to temporary recovery storage. They are absent from the active tree and were never a validated or committed implementation. Do not restore their former server/infrastructure design into new M0.

The personal/public repository, Ephorate name and intended `ephorate.dev` domain remain as requested. Domain purchase, hosting, license selection, public-example approval and new M0 assignment are not completed by this re-plan.
