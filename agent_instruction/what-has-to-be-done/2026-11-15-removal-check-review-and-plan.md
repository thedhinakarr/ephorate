# Removal-check pivot: review and implementation plan

Prepared 2026-11-15 for the owner and OpenCode implementation agents. Historical review note: the extraction/review session left the five supplied files unchanged. The owner subsequently accepted corrections and selected MIT; the revised root plan, decisions and [M1 handoff](2026-11-15-milestone-1-removal-check.md) now supersede tentative choices and pending-license statements below. The original ZIP remains unchanged. This note does not authorize or mark engine implementation complete.

## 1. Goal

Build Ephorate as a local test-dependency check for a committed code change: revert individual change units in scratch copies, run tests, and present the evidence as a reading list. First reconcile the new documentation with the actual repository and make the verdict contract precise. Then build the Python/pytest fixture engine and evaluate its usefulness before expanding it.

The useful claim is **which changes the executed tests demonstrably depend on**. Passing tests cannot distinguish unnecessary code from necessary but untested code. No verdict authorizes automatic deletion, approval or merging.

## 2. Context

### What was actually inspected

The owner deleted the previous working files and supplied `ephorate-pivot.zip`. Its SHA-256 is `73fcd9ecab8eb1e997b4d0b0a45639f715d051e0b68dab7ef3047dcdfade3aa6`. The archive contains five text files, totaling 66,262 uncompressed bytes:

- `AGENTS.md`
- `PROJECT_PLAN.md`
- `README.md`
- `index.html` (including its CSS and demo JavaScript)
- `agent_instruction/what-has-to-be-done/2026-11-15-pivot-to-removal-check.md`

All five were read in full. Archive CRC, paths, file types, and extracted-byte equality were checked. No archive entry overwrote an existing file. `.git` and `.gitignore` survived the owner's deletion and were left alone.

The local branch remains `main` at `03448228bf6838f4cd7d9903e9bc73236e91afc8`, the prior review-capacity merge. The working tree now contains the replacement documents and the owner's deletions. No commits, pushes, branch changes or product code were made for this request.

The previous index, chronological log, decisions, archives, starter ZIP and PDFs are absent from the working tree. They remain in [the immutable prior Git tree](https://github.com/thedhinakarr/ephorate/tree/03448228bf6838f4cd7d9903e9bc73236e91afc8). Do not restore them implicitly or execute the supplied handoff's `git mv` list. The immediate preceding direction was review capacity, following incident-risk scoring; the new handoff omits that intermediate history.

### Why the supplied M0 cannot run unchanged

It assumes a clean checkout with root PDFs, a starter, `.nojekyll`, an existing index/log, and the original incident-risk plan. Those assumptions are false. Its archive sequence also moves an old README into `archive/.../README.md` and then writes an archive notice to the same path. Its byte-identical replacement requirement conflicts with the corrections needed below. Treat these as proposed amendments for the next assignment, not silent substitutions.

### Research checks

The papers motivate testing the idea; none establishes Ephorate's utility:

- Chen/Stratton's current author-hosted version supports 35.7% more PRs opened, 56.1% longer submission-to-merge time, and 13.7% more resolved issues, with the issue estimate described as marginally insignificant. Specify the interval instead of calling it reviewer effort. The available author copy is dated 14 November; the deleted supplied PDF was the 9 November version. [Author PDF](https://fion.ac/jellyfish.pdf)
- Luo et al. report larger patches across 28 approaches on their resolved SWE-bench Verified instances, using per-instance comparisons aggregated by approach. That is not a claim that every individual patch is larger or that excess lines are unnecessary. [Primary paper, section V-C](https://arxiv.org/html/2608.13292v1)
- Banik et al. support 86,156 patches and 80.2% with weak/no explicit syntactic oracle signals. These are patch-diff signals, not an execution-based finding that 80% of entire test suites verify nothing; existing assertions and implicit oracles can be missed. Add the currently absent source link. [Primary paper, sections III and V](https://arxiv.org/html/2606.18168v1)
- Change-scoped mutation testing and reporting during review are established techniques. Keep the honest overlap with existing tools. [Google study](https://arxiv.org/abs/2102.11378)

PyPI availability could not be established from the attempted project-page lookup. An unsuccessful lookup is not proof that a name can be registered. No publishing account, package registration or license choice was made.

## 3. Files likely involved

For the corrective M0 assignment:

| File | Required change |
|---|---|
| `AGENTS.md`, `PROJECT_PLAN.md` | Correct history/status; adopt the clarified verdict and execution boundaries below |
| `README.md` | Narrow unsupported claims; label the reset/plan as awaiting acceptance; reconcile idle-test and network wording |
| `index.html` | Apply the same wording; fix citations and accessibility; preserve the design |
| Supplied pivot handoff | Replace stale inventory/archive operations and incompatible acceptance checks with the actual reset state |
| `agent_instruction/README.md` | New active source map, linked prior Git history, current status and next assignment |
| `agent_instruction/development-log.md` | Current chronology with a link to the exact previous log in Git; do not pretend old entries never existed |
| `docs/DECISIONS.md` | Record accepted contract corrections and why |
| New M1 handoff | Written after these contracts are accepted, before engine implementation |

Historical material stays in Git history by default. No PDF restoration, history rewriting or extra archive duplication is part of this plan. If archive snapshots are separately requested, use distinct direction-specific directories and `ARCHIVE.md` for notices, never overwrite an archived original.

For M1, create only `pyproject.toml`, `uv.lock`, `.python-version`, CI, `src/ephorate/`, and focused tests/fixture builders. Suggested modules are `cli.py`, `git.py`, `units.py`, `engine.py`, `report.py`, and `runners/pytest.py` with its explicitly loaded pytest plugin. No server, database, hosted dashboard, LLM, language extension or public Action yet.

## 4. Required implementation behavior

These are the recommended resolutions to freeze in M0. They deliberately narrow claims that the supplied design cannot establish.

### A. Correct M0, then stop

When assigned, create `pivot/removal-check` from the inspected current checkout without discarding the replacement files or owner's deletions. Reconcile the documents and new index/log/decisions. Keep the ZIP as the supplied source of record. Update the handoff to permit documented corrections rather than requiring byte identity after corrections. Validate text, links, demo and layout, then produce actual M0 work/results records. Do not build the engine in that assignment. Opening, pushing or merging a PR requires an assignment that includes those actions; the embedded sample prompt is not that authorization.

### B. Make verdicts mean the available evidence

| Case | Recommended outcome |
|---|---|
| Both clean-head baselines pass with identical collected node IDs and stable outcomes | Proceed; this observes stability twice, not proof of a nonflaky suite |
| Either baseline fails, its collection changes, or any outcome flips | Stop with baseline/instability failure; do not silently ignore tests in M1 |
| A previously passing test has a recognized call-phase assertion failure under one-unit removal | Candidate `held`; repeat the removal and a clean-head control before accepting the witness |
| Collection, setup or teardown error; structural exception; arbitrary runtime exception; incomplete report | `unjudged`, with phase/category recorded; never infer an assertion from traceback text |
| Missing, deselected or newly skipped baseline-passing tests | `unjudged`, even if pytest exits successfully |
| The same baseline-passing tests all execute and pass under removal | `loose`, reason `full_suite_passed_without_unit`; do not claim line coverage before M3 |
| Same parsed Python AST under the same interpreter | `inert` means AST-equivalent only, not proven behavior-equivalent |
| Unsupported file/language, failed patch application, timeout or exhausted budget | `unjudged`, with a stable reason code |

Any structural/setup/collection error or missing required test takes precedence over a candidate witness in the same trial. Stable baseline skips/xfails are disclosed but provide no witnesses. No-tests-collected is not a successful baseline. Unknown runner exit codes fail closed. Non-assertion behavioral failures can remain unjudged initially; favor honest incompleteness over false `held`.

Use a small pytest plugin loaded only for Ephorate's invocation. Capture exact node IDs, collected sets, run phase, outcome and exception class through documented hooks. The stock JUnit writer emits rendered failure text, not a dependable typed-exception field; JUnit alone cannot implement the proposed distinction. Keep JUnit as an optional compatibility artifact rather than the evidence authority. The plugin runs using the target's installed pytest and is not globally auto-registered. [JUnit source](https://docs.pytest.org/en/stable/_modules/_pytest/junitxml.html), [report hooks](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport), [exit codes](https://docs.pytest.org/en/stable/reference/exit-codes.html)

M1's single combined trial is group evidence only. An assertion after removing A and B does not prove both A and B are individually needed; a joint pass can also conceal interacting edits. Keep unresolved members `unjudged` and attach the group's result and witnesses. Do not claim a smallest group. Later delta debugging can establish minimality under its tested conditions, not a globally smallest group or behavioral correctness.

Limit the inert fast path to regular Python files present at the same path in both snapshots, with unchanged file metadata. An absent file is not equivalent to an existing empty module. Keep docstrings in AST comparisons and reject unsupported parses. Exclude shebang/encoding/tool-directive edits from automatic inert treatment. Even ordinary comment/position changes can matter to source-reading tools; label the limited evidence and let reviewers expand it. Python's AST also varies by interpreter version. [AST reference](https://docs.python.org/3/library/ast.html)

### C. Keep execution separate from the user's checkout

- M1 checks committed `HEAD` against an explicitly resolved base commit. Accept `--base REF`; for the default, use the merge base with an already-present `refs/remotes/origin/HEAD`. If that reference or commit objects are missing, require explicit input; never fetch or guess a branch name.
- Reject staged, unstaged and untracked changes in M1. No dirty-tree override yet. Resolve and record immutable SHAs before work. Inspect status with optional Git locks disabled so inspection does not refresh the source index. [Git status](https://git-scm.com/docs/git-status)
- Use independent temporary clones, not linked worktrees. Clone only from the validated local repository, without hardlinks, shared object stores or alternates, using an owned empty Git template and detached checkout. Verify base/head objects were copied. Never create source refs to make a missing object reachable. This costs disk/time but avoids shared refs and worktree administration. [Git clone](https://git-scm.com/docs/git-clone), [worktree sharing](https://git-scm.com/docs/git-worktree)
- Allow local Git transport only; disable lazy fetch, hooks, fsmonitor and global/system configuration for controlled Git subprocesses. Reject partial/promisor repositories, submodules, symlink entries and active checkout filters/LFS initially. Do not alter source configuration. Recreate baseline and trial trees so one test run's generated files cannot contaminate the next. [Git controls](https://git-scm.com/docs/git), [hooks](https://git-scm.com/docs/githooks), [filters](https://git-scm.com/docs/gitattributes)
- Execute an argument vector with `shell=False`; initially accept direct pytest or `python -m pytest`, not shell pipelines or dependency-install wrappers. Dependencies must already exist. Require a declared source root (`.` or `src`) and verify loaded subject-module origins belong to the scratch copy. An editable install pointing to the original checkout otherwise produces misleading passes. [pytest import behavior](https://docs.pytest.org/en/stable/explanation/pythonpath.html)
- Scratch copies are not a security sandbox. The M1 engine executes trusted test code. Ephorate performs no network operations; arbitrary subprocess tests can still use the network or absolute paths. Do not promise otherwise. Untrusted public replay needs an isolated runner before execution in M2.
- Apply unit reversals only inside owned scratch copies. On timeout or interrupt, terminate the owned process group before cleanup; never delete unrelated temporary paths. SIGKILL/power-loss cleanup cannot be guaranteed; report owned leftovers for recovery rather than making an absolute promise.
- Write JSON to stdout and the human summary to stderr by default. An optional explicit JSON file must be outside the checked worktree and must not overwrite an existing file without explicit user action. This keeps the input worktree unchanged while still delivering reports.

### D. Keep the first engine small

The execution path is CLI → Git snapshot/diff → units → pytest adapter → verdict reducer → report. Git access stays in `git.py`; test-runner access stays in the adapter. Suggested interfaces for the M1 handoff:

- `cli.main(argv: Sequence[str] | None = None) -> int`
- `git.resolve_change(repo: Path, base: str | None) -> Change` (repository root, base/head SHAs, changed-path metadata)
- `units.split_change(change: Change) -> list[Unit]` (stable ID, path, base/head ranges, addition/deletion counts and reverse patch)
- `runners.pytest.run_trial(root: Path, argv: Sequence[str], timeout_s: float) -> TrialResult` (collected IDs, phase outcomes, exception classes, exit/timeout/completeness)
- `engine.check(change: Change, config: CheckConfig) -> CheckReport`
- `report.write_json(report: CheckReport, stream: TextIO) -> None`

Use plain typed records; do not add a plugin framework or generic workflow layer. Before implementing M1, its handoff must enumerate these records and the JSON schema, including reason codes and lifecycle states; the functions above are the module boundaries, not a claim that the engine exists.

Start with full test runs, one job, and deterministic path/hunk ordering. Each non-inert subject unit is one `git diff -U0` hunk. Reverse against the same head snapshot each time, never cumulatively. Preserve base/head coordinates and count changed lines as additions plus deletions, matching the illustration. Handle whole-file additions/deletions explicitly. Rename metadata cannot be reversed as an arbitrary standalone text hunk: initially represent it as delete/add operations and disclose unsupported grouping, or mark the unresolved rename unjudged.

Judge-file detection must cover pytest-discovered test modules, configured patterns, `conftest.py`, pytest configuration and workflows. Judge status wins any pattern overlap, and ambiguity is unjudged. Record added, modified, renamed and deleted judge files in M1; the supplied plan incorrectly defers mandatory judge-change reporting to M4. Other/configuration files are unsupported by the first analysis, not inherently untestable.

Idle-test evidence applies to both added and modified tests. Map cases to changed test definitions; if dynamic generation makes that mapping ambiguous, record unknown. A full-subject-removal trial must run the same relevant tests successfully before calling any test idle. This means passing with changed subject units reverted, not independence from changed configuration, tests or the entire change. Collection failure, unavailable cases or skips are not idle evidence. A passing idle test can still be a useful regression test; do not instruct agents to delete it automatically.

Bound runtime in M1 rather than deferring all safeguards to M3: serial execution, 50 subject units, 15-minute total budget and per-run timeout `max(30 seconds, 3 × slower baseline duration)`, capped by remaining total budget. Give each baseline a 5-minute ceiling. Leave over-budget units unjudged in stable order. Expose these limits in configuration and report them. With N individual trials and H confirmed witnesses, the conservative upper test-run count is roughly `N + 4 + 2H`, including two baselines, one group trial, one idle trial and witness controls. Measure actual cost; do not sell speed before M2.

The initial JSON has a version, base/head SHAs, tool/interpreter/runner/config provenance, baseline evidence, unit and group records, idle evidence, judge changes, completion/budget status and timings. Stable IDs and sorted collections make unchanged deterministic fixtures reproducible after removing timing fields. Do not embed temporary paths or random run IDs in semantic output. Cache nothing in M1.

Keep the supplied exit-code contract: 0 completed, 1 completed with a matching `--fail-on` condition, 2 usage/baseline/execution failure. Implement the minimal `--fail-on loose,unjudged,idle` switch with M1's reporting rather than describing an exit code that cannot occur until M5. A completed partial result can contain unjudged units and says so. M5 adds agent instructions and assesses how they are gamed.

Current tooling candidates checked against primary metadata: Python 3.15.2 for development, supported stable Python minors 3.11–3.15, uv/uv_build 0.13.8, pytest 9.2.0, Ruff 0.17.5 and mypy 2.4.1. One installed `src/ephorate` package, no third-party CLI runtime dependencies, and the console script `ephorate.cli:main`. Lock and test the combination during the M1 assignment; metadata availability is not runtime verification. [Python support](https://devguide.python.org/versions/), [Python release](https://www.python.org/downloads/release/python-3152/), [uv release](https://github.com/astral-sh/uv/releases/tag/0.13.8), [build backend](https://docs.astral.sh/uv/concepts/build-backend/), [pytest](https://pypi.org/project/pytest/9.2.0/), [Ruff](https://pypi.org/project/ruff/), [mypy](https://pypi.org/project/mypy/)

### E. Preserve the evidence gate

M2 follows accepted fixtures. Obtain owner approval of the repository list and selection rule before cloning outside repositories. Aim for at least 30 merged, detectably agent-authored PRs across 10 repositories, with offline suites. Record every selected attempt, exclusions and failures so easy repositories do not silently define success. Use isolated disposable execution without secrets for public test code.

Audit at least 30 loose and 30 held units, if available; report shortfalls rather than inventing samples. Separate unnecessary code, necessary-but-untested code, false verdicts, and shallow assertions. Report PR-level median/spread of loose/inert changed-line shares, unjudged and group-only shares, wall time and witness-confirmation failures. Group witnesses are not individual held observations. Two baselines cannot certify nonflakiness. The owner makes the M2 go/no-go decision from this evidence, even if figures look favorable.

Only after that gate: M3 selection/parallelism/cache; M4 finer units and attribution; M5 agent loop; M6 Action; M7 HTML; M8 second language; M9 release. No-context coverage must fall back to a full trial: import/startup work may be recorded under the empty context. Do not declare zero-context units loose without execution. Cache identity must eventually include environment, interpreter, dependency state and configuration, not merely tree and command. [Coverage contexts](https://coverage.readthedocs.io/en/latest/contexts.html)

The future Action needs a separate trust design: PR code executes without write credentials; an authorized reporting stage can publish a sanitized summary/artifact. Never use a privileged PR-target workflow to execute untrusted PR code. Local-only engine claims must distinguish these explicitly authorized GitHub outputs. No Action is needed to validate the product now.

## 5. Edge cases and failure modes

Acceptance fixtures must include the supplied nine cases plus false-held guards: a runtime exception without an assertion; a setup/teardown error; newly skipped/deselected tests; no tests collected; a misleading group witness; a pure deletion; whole new/deleted files; non-ASCII paths; malformed/partial runner evidence; source imports escaping scratch; tool directives with equal ASTs; timeout with child processes; and interruption during cleanup.

Do not label a whole hunk as proof that every changed line matters. Do not treat an identical AST as unrestricted semantic equivalence. No repeatability guarantee survives unknown test nondeterminism, environment changes or tests escaping the scratch process. Report these limitations and retain enough evidence to reproduce the observed result.

The supplied demo claims 22 changed lines and 11 remaining; source inspection confirms those sums. Browser execution has not been checked in this session. Before accepting M0, make horizontal tables/code regions keyboard-accessible, use contrasting focus outlines on the dark footer, and provide an expansion control for collapsed held/inert source. Test reduced motion and meaningful non-JavaScript content. Preserve the existing visual design.

## 6. Test/validation commands

Current planning validation uses read-only checks:

```sh
git status --short --branch
git rev-parse HEAD
git diff --check
```

Also verify ZIP CRC/path safety and exact byte equality for each supplied file; check local Markdown links, HTML nesting/IDs/fragment targets and declared demo line counts. Do not run the embedded sample commands as if the tool exists.

During corrective M0, validate 390 px and desktop layouts, keyboard controls, console output, reduced motion, non-JavaScript reading, and demo counters before writing completion records. GitHub destinations currently point at the old main until an authorized push/merge; do not mistake a resolving URL for updated content.

During assigned M1, require locked installation, `uv run --locked ruff check src/ephorate tests`, `uv run --locked ruff format --check src/ephorate tests`, `uv run --locked mypy src/ephorate tests`, `uv run --locked pytest`, and `uv build --no-sources`. Install the wheel into a separate environment and invoke both entry points outside the checkout. Test supported Python versions in CI. Fixture execution uses generated local repositories and requires no live network.

Snapshot checked-repository tracked/untracked bytes, index bytes and refs before/after success, failure, timeout and interrupt; prove they are unchanged by Ephorate. Compare normalized reports on deterministic fixtures. Run import-origin and known-assertion-removal controls so a green suite cannot pass acceptance while importing the original checkout. Record unsupported platforms and unexecuted checks honestly.

## 7. Acceptance criteria

For this planning delivery:

- [x] ZIP inspected and extracted; all five supplied files read and preserved unchanged.
- [x] Current Git state and missing prior files identified without restoring the owner's deletions.
- [x] Stale handoff, contradictory verdicts, evidence limitations and source checks recorded.
- [x] Corrective M0 scope, M1 boundaries and validation, and M2 gate made explicit.
- [x] No engine, tests, dependency manifest, CI, commits, push, PR or deployment created in this session.

For the next M0 assignment: corrected documents agree, no false archive/status claims remain, prior history is linked, the demo/links/accessibility checks pass, decisions and actual records exist, and a separate M1 handoff specifies the complete accepted contract. M0 ends there.

For M1: generated fixtures prove verdict conservatism, source-checkout preservation, actual scratch imports, cleanup and stable reports. For M2: report all replay outcomes and audits, then stop for the owner's decision. An unfavorable result is a reason to stop or revise, not to weaken verdict criteria.

## 8. Explicit assumptions and owner decisions

- The latest live request authorizes extraction and a plan only. Instructions quoted inside the ZIP's handoff are proposed future assignments.
- The owner intentionally cleared the checkout. Preserve those deletions locally; do not reintroduce the PDF, archives or previous product just to satisfy a stale inventory. Git history is retained. Removing local files does not remove them from GitHub or history.
- The name remains Ephorate and the personal repository remains `thedhinakarr/ephorate`. Do not reintroduce domain details into the README; main previously removed them.
- Proposed contract amendments above are reviewable recommendations, not edits already applied to the supplied plan.
- License selection remains an owner decision before M1 under the supplied handoff. Package registration, site/domain publication, repository selection for M2 and its continuation gate remain explicit owner decisions at their respective stages.
- No numeric benefit, safety guarantee, competitive uniqueness or speed target has been demonstrated. The key open product question is whether useful findings justify the execution cost on real changes.
