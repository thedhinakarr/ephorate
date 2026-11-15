# Ephorate

**Find out where code review will break as your agents write more code, and what would fix it.**

Ephorate is a planned review capacity simulator: a Python CLI and GitHub Action that will use GitHub history to map demand and shared reviewer capacity, test forecasts against the past, and compare possible fixes.

**Nothing in the new product is built yet.** This repository contains the plan, first handoff, research references, and a static landing page. There is no working collector, capacity model, report generator, or Action. The interrupted skeleton for the former product was removed from the active tree before this re-plan.

[Public personal repository](https://github.com/thedhinakarr/ephorate).

## Why this direction

The motivating research describes a code-review bottleneck after coding-agent adoption: more work arrives, while review depends strongly on people familiar with the codebase. The proposed product asks whether a team's own history can forecast where that constraint will bind and whether a proposed fix would help.

The paper does not validate this product. GitHub timestamps measure elapsed workflow time, not reviewer working hours; historical throughput is an effective-capacity proxy. The backtest is the credibility gate. Claims that no competitor offers this capability remain a market hypothesis, not a verified fact.

## Planned workflow

1. **Read history.** Collect one repository's metadata for a default 12-month reporting window, with qualification warm-up and the initial open queue. Detect known coding agents, keep dependency bots separate, and disclose undetected agents.
2. **Map and measure.** Assign paths to areas, identify historically qualified reviewers, and measure arrivals, familiarity, waiting, elapsed review time, shared load, and human review coverage.
3. **Check against the past.** Fit on the first nine months and predict the last three. Compare waiting predictions with the previous quarter's observations, and check coverage and backlog too.
4. **Run scenarios.** Increase agent arrivals and show per-area waiting, backlog, demand relative to capacity, and pressure associated with lower review coverage. Every forecast includes its backtest error and limits.
5. **Test fixes.** Compare reviewer eligibility, explicitly assumed review exemptions, agent PR limits, and workload reallocations. Show spillovers, deferred work, and coverage tradeoffs.
6. **Write artifacts.** Produce self-contained HTML, versioned JSON, and separate suggested `CODEOWNERS` changes. The tool will never apply them.

## Read-only and private by design

- No changes to GitHub settings, PRs, reviews, labels, or ownership files.
- No Ephorate server, telemetry, or transfer to a third-party analysis service. Metadata stays in the operator's local store or CI workspace/artifacts; local execution necessarily stores metadata on the operator's machine.
- No source files are collected. The sole approved file-content exception is `CODEOWNERS` configuration. Incidental text or code in REST metadata responses is discarded in memory and never retained or forwarded.
- No LLM is required or planned.
- Tokens come from the environment and never appear in reports or logs.

## This is not a people-performance tool

The report describes the review system so a lead can change it. Default views are per area and hide identities. Optional person detail exists only to show shared workload or name a possible reviewer; one `--people hide` option suppresses it across all outputs. Ephorate will not rank people, label them slow, or grade performance.

GitHub does not provide job levels. Seniority requires an explicit team-supplied mapping. Otherwise any relevant measure is labeled **tenure in this repository**, with observation-window limits shown.

## Where it stands

| Milestone | Deliverable | State |
|---|---|---|
| 0 | Installable CLI, SQLite initialization, tests and CI | Handoff ready; not implemented |
| 1 | Resumable GitHub metadata collector | Planned |
| 2 | Area mapping and auditable measurements | Planned |
| 3 | Discrete-event model and time-ordered backtest | Planned; mandatory owner gate |
| 4 | Scenarios and proposed fixes | Gated on M3 and owner approval |
| 5 | HTML/JSON reports and GitHub Action | Planned |
| 6 | Approved, identity-masked public examples | Planned |

The local store will be **SQLite**, using Python's standard library. M0 will need no runtime dependencies. No FastAPI, database server, analytics service, workflow cluster, cloud infrastructure, or hosted application is part of this plan.

## Start here

- [Standing rules](AGENTS.md)
- [Master plan](PROJECT_PLAN.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Recorded decisions](docs/DECISIONS.md)
- [First implementation handoff](agent_instruction/what-has-to-be-done/2026-11-15-milestone-0-review-capacity.md)
- [Repository index](agent_instruction/README.md) and [development log](agent_instruction/development-log.md)

The owner must assign new M0 before implementation begins. Setup instructions will be added when it is implemented and checked.

The former plan, handoff, and pitch are preserved in [the archive](archive/2026-11-incident-risk/ARCHIVE.md). The downloaded `ephorate/` starter and `ephorate.zip` remain historical references, not an implementation root or publishing instruction.

## Research and licensing

Chen, Fiona, and James Stratton. *Artificial Intelligence in the Firm: Bottlenecks in Software Production*. The [repository copy](jellyfish.pdf) is dated 9 November 2026; the [authors' current copy](https://fion.ac/jellyfish.pdf) was dated 14 November when checked on 15 November. See the [author's page](https://fion.ac/) for attribution.

The owner chose to keep this third-party PDF in the public repository. Removing it from the current tree later would not remove it from Git history. Inclusion does not assert redistribution rights or put it under a future project license.

The project's license has not been chosen. Public visibility alone is not an open-source license.
