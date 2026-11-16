# Ephorate agent index

Updated 2026-11-16. Ephorate's Milestone 1 local removal-check engine is implemented and pushed to the personal repository on `implementation/removal-check-m1`. The [website is live](https://thedhinakarr.github.io/ephorate/) on GitHub Pages. See [what was done](what-was-done/2026-11-15-milestone-1.md), [local engine results](what-was-the-result/2026-11-15-milestone-1.md) and [publication results](what-was-the-result/2026-11-16-github-pages.md); stop before M2 replay.

## Start here

1. [Standing rules](../AGENTS.md)
2. [Master plan](../PROJECT_PLAN.md)
3. [Decisions](../docs/DECISIONS.md) and [development log](development-log.md)
4. [Milestone 1 contract](what-has-to-be-done/2026-11-15-milestone-1-removal-check.md) and its implementation/results records

The master plan states the product boundaries; the M1 handoff specifies the exact engine contract and validation. If they conflict, reconcile the concrete discrepancy before coding. The [review note](what-has-to-be-done/2026-11-15-removal-check-review-and-plan.md) preserves the findings that led to these corrections, and the [corrected reset handoff](what-has-to-be-done/2026-11-15-pivot-to-removal-check.md) replaces the stale archive instructions in the ZIP.

## Current source map

| File | Meaning |
|---|---|
| `AGENTS.md`, `PROJECT_PLAN.md` | Accepted removal-check rules, milestones and owner gates |
| `README.md` | Product overview and truthful status |
| `index.html` | Static illustrated concept; no engine integration |
| `LICENSE` | Owner-selected MIT license for Ephorate's own material |
| `docs/DECISIONS.md` | Resolved engineering and scope choices |
| `ephorate-pivot.zip` | Unchanged supplied replacement bundle; historical instructions inside are not an active assignment |
| `agent_instruction/what-has-to-be-done/` | Review/reset records and next implementation handoff |

The owner intentionally cleared the previous working files. Prior plans, PDFs, archives and chronological entries remain at [commit 0344822](https://github.com/thedhinakarr/ephorate/tree/03448228bf6838f4cd7d9903e9bc73236e91afc8). Do not restore deleted artifacts to satisfy the old handoff, claim the local archive exists, or rewrite Git history. The immediately previous direction was review capacity, preceded by incident-risk scoring.

## Milestone state

| Milestone | State |
|---|---|
| M0 documentation reconciliation | Plan/rules/copy and M1 assignment prepared; no engine work |
| M1 Python/pytest engine on fixtures | Implemented and pushed; local and remote CI outcomes recorded |
| M2 real-PR replay | Owner approves repositories first; ends at an explicit go/no-go |
| M3–M9 | Gated speed, precision, agent loop, Action, reports, second language and release |

Website accessibility changes and browser checks were completed for the owner's explicit Pages deployment. The [publication record](what-was-done/2026-11-16-github-pages.md) describes the content-only `gh-pages` branch; the results record states the actual checks and their limits. The Python alpha package has not been released to a registry. `main` remains on the prior direction; no merge was assigned.

Handoffs use the eight-section OpenCode format. Write `what-was-done/` and `what-was-the-result/` records only for actual implementation and checks. Keep the current log chronological; earlier entries are linked in Git because the owner removed their working copy. Do not log credentials, raw sensitive process output or private code.
