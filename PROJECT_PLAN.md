# Ephorate project plan

Reconciled 2026-11-15 after the owner accepted the removal-check review corrections. The owner has now explicitly assigned **Milestone 1 implementation**. Follow the M1 handoff and stop before M2. MIT was selected by the owner and recorded in `LICENSE`.

M1 is implemented. See the [implementation record](agent_instruction/what-was-done/2026-11-15-milestone-1.md) and [validation results](agent_instruction/what-was-the-result/2026-11-15-milestone-1.md): final fixture and fresh-checkout suites passed; remote CI/Linux execution remain unobserved. M2 has not started.

The previous directions were incident-risk scoring and then review-capacity simulation. The owner deleted their working files before supplying `ephorate-pivot.zip`; they remain in [Git history](https://github.com/thedhinakarr/ephorate/tree/03448228bf6838f4cd7d9903e9bc73236e91afc8), not an existing local archive. Do not restore deleted material or execute the ZIP's stale archive instructions.

## 1. Purpose and scope

Ephorate asks **which test fails when this part of a committed change is reverted?** It runs removal trials in independent scratch copies and produces a reading list for agents and reviewers. It reports evidence; it does not delete code, approve changes or merge pull requests.

Passing tests cannot distinguish unnecessary code from necessary but untested code. A failing assertion shows a test's dependence on a trial, not correctness or safety. Identical syntax trees are a limited observation, not a proof of identical behavior. These limits are part of the product contract.

M1 is a serial Python/pytest engine on generated local fixtures. M2 measures usefulness, false findings and execution cost on owner-approved real PRs. Everything beyond M2 requires an explicit go/no-go. No language model, server, database, dashboard, telemetry, network dependency installation or hosted backend is planned.

## 2. Definitions

| Term | Contract |
|---|---|
| Change | Committed `HEAD` compared with a resolved base commit. Explicit `--base` names the base itself. Without it, use the merge base with locally available `refs/remotes/origin/HEAD`; missing/ambiguous references require explicit input, not fetching or guessing. |
| Judge file | Tests discovered by pytest or protected test patterns, plus conftest, test-runner configuration and CI workflows. Judge status wins overlaps. Judge files are never reverted; additions, modifications, renames and deletions are reported in M1. |
| Subject file | Supported regular Python source outside the judge and excluded/other categories. |
| Other file | Unsupported language, configuration/data, migration, lockfile, generated or otherwise excluded content. Report it as unjudged; do not claim such content is inherently untestable. |
| Unit | One zero-context hunk for a supported modified file; a whole-file reversion for a new/deleted file. File existence is part of a whole-file trial. Report base/head ranges and additions plus deletions. Rename detection is disabled initially; represent rename content as delete/add. |
| Baseline | Two fresh clean-head runs with identical collected node IDs and stable outcomes, at least one passing test, and no errors/failures. Instability stops M1; no flaky-test exclusion. Two passes do not prove nonflakiness. |
| Structural failure | Collection/load/syntax failure or one of the explicit structural exception classes in the handoff. It is not assertion evidence. Other unexpected runtime exceptions also fail closed. |
| Witness | A baseline-passing test with a recognized call-phase assertion failure in the single-unit trial, reproduced by another removal trial with the same witness, followed by a passing clean-head control. Phase, exception and provenance are recorded. |
| Group | The exact set of structurally failing units removed in M1's one combined diagnostic trial. Its outcome is collective evidence only; it does not promote individual verdicts or establish a smallest group. |
| Idle-test evidence | An added or modified test still passes with all changed subject units reverted, while judges and other files remain at head. Other tests may fail recognized assertions, provided collection is complete and no structural/runtime/setup/teardown or integrity error invalidates the trial. This is not independence from the entire change or proof that a regression test should be deleted. |
| Reading list | Loose/unjudged units, group-only evidence, idle candidates and changed judges. Tests remain reviewable even when units are held; inert/held content remains expandable. |

Every changed non-judge unit has exactly one verdict. File-level records also describe unsupported and judge changes so none disappear from totals.

| Verdict | Required evidence |
|---|---|
| `held` | An individually confirmed assertion witness, with no higher-priority uncertainty/error in its trial and successful head control. It refers to the unit, not every line within it. |
| `loose` | The complete configured cohort executes with all baseline-passing tests passing and stable non-passing baseline outcomes. Reason: `full_suite_passed_without_unit`; no claim about executed lines before coverage exists. |
| `inert` | Same parsed AST for head and head with that single unit reverted, for an eligible same-path regular Python modification with unchanged file metadata. Preserve docstrings; exclude directive/shebang/encoding edits and unsupported parses. No test trial is required for this limited classification. New/deleted files cannot take this fast path. |
| `unjudged` | Unsupported input, non-assertion/structural error, missing or newly skipped tests, malformed/incomplete evidence, timeout, budget limit, failed application, failed confirmation, or group-only attribution. Record the exact reason. |

Uncertainty overrides assertions: collection/setup/teardown errors, missing/new/deselected cases, changed skips/xfails, malformed reports and unknown outcomes cannot produce held or loose. Stable skips/xfails provide no witnesses. A passing or failing combined group never silently changes a member's individual verdict. A failed executed head control invalidates previous test-derived held/loose results, stops further trials and yields an instability failure; insufficient budget to start a control leaves only its unconfirmed candidate unjudged. The M1 handoff defines precedence and the complete reason enums.

## 3. Execution boundary

M1 checks a clean committed tree only: reject staged, unstaged and untracked changes. There is no dirty-tree override. This restriction applies to repositories checked by the future tool; it is not permission for implementation agents to discard the owner's present documentation changes.

Inspect source Git state without optional locks. Resolve immutable SHAs before copying. All Git operations go through `src/ephorate/git.py`. Use independent temporary local clones with detached head, no hardlinks, alternates, shared object store, inherited hooks or fsmonitor. Linked worktrees share administration and are not the selected design. Allow local transport only, disable lazy fetching, and reject unsupported partial clones, submodules, symlinks and checkout filters/LFS. Missing objects fail instead of fetching or creating source refs.

Each baseline/trial starts from a fresh head snapshot. Apply reversals only there, never cumulatively between units. Test commands use argument arrays with `shell=False`, the same interpreter as Ephorate, and the pinned supported target pytest. M1 supports native synchronous pytest function/method items; unittest, doctest, subtest and custom/distributed runner protocols fail explicitly instead of being silently omitted. In particular, unittest setup/teardown can execute inside pytest's call phase, so it cannot share the simple assertion classifier. No shell pipelines, install wrappers, xdist, automatic dependency setup or reusable dirty trial directories. Verify that observed subject imports resolve inside scratch; reject an observed editable-install fallback to the original checkout. Origin validation covers modules visible in the pytest process at the observer checkpoints. It cannot establish where subprocesses or native extensions loaded code, or detect modules removed between checkpoints.

These are trusted-code checks, not an OS security sandbox. Ephorate itself does not call the network or write the original checkout. Arbitrary test code can access absolute paths or the network; public replay requires isolated disposable execution without secrets. Handle timeouts and ordinary interrupts by terminating the owned process group before removing owned temporary files. SIGKILL/power loss can leave recoverable scratch data; do not promise impossible cleanup guarantees.

## 4. Evidence, algorithm and outputs

Use an explicitly loaded pytest observer through documented hooks to capture collected node IDs, file locations, phase outcomes and exception information. The standard JUnit writer supplies formatted failures, not reliable typed exceptions, so it is not the verdict authority. No globally auto-registered plugin, traceback-text classifier, or third-party runtime dependency is needed. The observer uses the target's installed pytest. JUnit interoperability can be added later when a runner needs it.

The M1 sequence is fixed:

1. Validate invocation, configuration, input Git state, local objects, supported checkout behavior and output destination.
2. Resolve changed paths and provisional units; perform two fresh-head baselines and finalize judge classification from collection evidence.
3. Reject invalid or unstable baseline evidence. Identify eligible AST-equivalent modifications.
4. Run individual units in stable path/range order using the complete suite. Confirm candidate held results with a repeated removal and a fresh head control.
5. Run at most one combined diagnostic trial for structural units; preserve individual unjudged results.
6. Run the all-subject-reverted idle trial when complete reversal and budget permit. Dynamic/ambiguous test mapping and incomplete runs are unknown, never fabricated idle results.
7. Emit a versioned report with full provenance and a reading list. No automatic source change follows a verdict.

Defaults: one job; 50 subject units; analysis wall budget 900 seconds; each baseline at most 300 seconds; later trial timeout `max(30 seconds, 3 × slower baseline duration)`, bounded by remaining analysis budget. Final source verification gets a separate 30 seconds, then output/cleanup another 30 seconds; child termination may overrun the analysis budget. These allowances cannot schedule more tests. Budgets apply from M1; optimization waits until M3. The handoff fixes count/eligibility and partial-run semantics. Report every over-budget unit as unjudged; never silently truncate demand or evidence.

JSON goes to stdout, human summary to stderr. An explicit JSON path must be outside the checked worktree and must not replace an existing file. No raw test output, captured locals, source content or absolute scratch paths in the normal JSON. Record schema/tool/interpreter/runner/config versions, SHAs, files/units, baseline, trial and witness evidence, groups, idle evidence, judges, budgets, completion status and timings. Stable IDs and sorted records make deterministic fixtures reproducible except for timing fields; uncontrolled tests/environments may differ.

Exit codes: `0` for a completed check without a requested fail-on match; `1` for a completed check matching `--fail-on loose,unjudged,idle`; `2` for invocation/baseline/infrastructure failure; `130` for SIGINT and `143` for SIGTERM after attempted cleanup. A partial report can contain unjudged findings and must say why. The CLI and TOML key set, validation, adapter protocol, exact JSON records, reason codes and interrupt semantics are specified in the [M1 handoff](agent_instruction/what-has-to-be-done/2026-11-15-milestone-1-removal-check.md).

## 5. Stack and implementation boundaries

One installed `src/ephorate` Python package, a console entry point and `python -m ephorate`; standard-library runtime. `argparse`, `subprocess`, `ast`, `tomllib` and JSON are sufficient. Pytest is an external requirement of the checked environment and a development dependency, not a general runtime dependency.

Pins and the supported interpreter matrix are fixed in the M1 handoff and implemented in `pyproject.toml`, `uv.lock` and CI. The [M1 results record](agent_instruction/what-was-the-result/2026-11-15-milestone-1.md) distinguishes observed local checks from configured but unobserved remote CI. Version metadata alone is not runtime evidence.

The product uses the owner's selected MIT license. This does not relicense third-party research or historical assets. PyPI name registration remains unverified; it is not a prerequisite for local fixture development. The site remains one root HTML file; engineering records live in `docs/`.

## 6. Milestones and acceptance

### M0 — Reconcile the reset and plan

Record the actual cleared checkout and history; update rules, plan, copy, index/log and decisions; replace the stale reset handoff; prepare the decision-complete M1 assignment. Preserve the supplied ZIP and intentional deletions. Do not resurrect local archives, PDFs or old product scaffolds. No engine code.

Acceptance for the planning portion: definitions agree across active documents, the new handoff is complete, MIT is recorded, links/structure pass inspection, and no engine/package/CI files exist. Marketing accessibility, browser demonstration and publication QA remain tracked work before site publication; they do not authorize implementation or block the separately assigned fixture engine. No completion record may imply those checks ran when they did not.

### M1 — Engine on generated fixtures

Implement only [the OpenCode handoff](agent_instruction/what-has-to-be-done/2026-11-15-milestone-1-removal-check.md): package/checks/CI; safe committed snapshots; classification and reversible units; stable baselines; structured pytest evidence; conservative verdicts and witness controls; group observation; idle evidence; changed-judge reporting; bounded execution; terminal/JSON and minimal fail-on.

Acceptance: all specified fixtures obtain their expected results; original worktree bytes, index and refs are preserved across success/failure/timeout/ordinary interrupt; the observer rejects out-of-scratch origins within its documented in-process checkpoint scope; deterministic normalized reports repeat; lint/types/tests/build and installed-wheel smoke checks pass outside the checkout. CI tests the supported interpreter/platform matrix without live network-dependent application tests. Report actual commands/results and stop before M2. No cache, parallelism, coverage selection, Action, HTML generator or language extension.

### M2 — Replay and owner decision

The owner approves the repository list and selection rule before cloning outside repositories. Target at least 30 merged PRs with detectable agent authorship across at least 10 Python/pytest repositories with offline suites. Use isolated disposable runners without secrets. Prespecify sampling and record every attempt, exclusion and failure.

Audit at least 30 loose and 30 individually held units when available; disclose shortfalls. Separate unnecessary code, needed-but-untested code, false verdicts, shallow assertions and group-only findings. Report PR-level median/spread of changed-source-line shares, unjudged coverage, runtime/trial counts and confirmation failures. The denominator is additions plus deletions in supported changed source, with exclusions visible.

Write `docs/REPLAY_REPORT.md` with methods, repository context, reproducibility, limitations and PR links rather than vendored code. **Stop for the owner's go/no-go**, regardless of favorable results. If useful findings are rare or unreliable, or execution cost is excessive, recommend revision or stopping rather than weakening the verdict contract.

### M3 — Speed

Add coverage-context selection, `--full`, parallel trials and cache. Missing/empty contexts fall back to full trials, including import/startup execution; absence of mapped tests is not proof of loose code. Cache identity includes interpreter, dependencies, configuration, observer version and environment inputs, not only tree/command. Compare selected/full verdicts across all fixtures and replay attempts; publish differences and keep unsupported cases conservative.

### M4 — Precision

Add finer definition-boundary units and bounded delta debugging. Describe tested minimality accurately; do not promise global smallest groups or infer individual necessity from collective witnesses. Add adversarial fixtures and rerun the replay set, reporting changes in verdicts. Judge-change reporting already exists in M1.

### M5 — Agent loop

Stabilize the existing versioned report and fail-on contract; supply small instructions for coding agents. Direct agents to inspect loose findings and delete or add meaningful tests, without altering existing tests to manufacture a verdict. Demonstrate on fixtures and record shallow-test gaming. No LLM is embedded in Ephorate.

### M6 — GitHub Action

Keep test execution separate from write credentials. Run untrusted PR code only in the restricted execution stage; an authorized reporting stage posts a sanitized comment/job summary and allowed artifacts. Never execute untrusted PR code with privileged PR-target credentials. Document fork behavior, permissions and authorized outputs. These GitHub outputs are distinct from the local engine's no-upload behavior.

### M7–M9 — Reports, second language and release

M7 adds self-contained offline HTML with expandable evidence and source; M8 adds TypeScript through a runner-specific evidence adapter and parser verified against its tests; M9 packages the accepted tool, demo and Action for an explicitly authorized release. PyPI publishing, website/domain publication and external release actions require owner assignments. The site uses measured replay results only after they exist.

## 7. Risks and validation discipline

- **Weak utility:** real changes may contain few useful loose/inert units; M2 tests this before integrations.
- **False confidence:** error phases, missing tests, structural exceptions, collective witnesses and AST equality can be overstated; retain conservative reasons and exact evidence.
- **Test nondeterminism and environment drift:** repeat controls reduce uncertainty but cannot eliminate it. Report instability rather than silently ignoring tests.
- **Wrong source imports:** editable installs or import hooks can test the original source. Verify origin and fail closed on ambiguity.
- **Execution cost:** serial full-suite runs and confirmation controls are expensive. Apply limits immediately and measure cost before optimizing.
- **Untrusted test execution:** scratch copies are not sandboxing. Restrict M1 to trusted fixtures; isolate later public replay.
- **Incomplete test classification:** protect discovered/custom tests, conftest and configuration; resolve ambiguity as unjudged.
- **Marketing overstatement:** research supports investigation, not this product's effectiveness; keep the narrower claims and primary citations in the README/site.

Tests use generated local repositories, not vendored projects. Record checks that ran and those that did not. Never create engine completion or replay results before they exist.

## 8. Current sources and owner decisions

Owner decisions: new removal-check direction, accepted corrections, MIT, then explicit M1 implementation after the planning handoff. Remaining gates: approval of M2 repositories and continuation; publishing/release actions. The owner's reset is intentional and Git history remains intact.

Primary technical references: [Git status](https://git-scm.com/docs/git-status), [Git clone](https://git-scm.com/docs/git-clone), [Git worktree](https://git-scm.com/docs/git-worktree), [pytest reporting hooks](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_makereport), [pytest JUnit writer](https://docs.pytest.org/en/stable/_modules/_pytest/junitxml.html), [pytest imports](https://docs.pytest.org/en/stable/explanation/pythonpath.html), [coverage contexts](https://coverage.readthedocs.io/en/latest/contexts.html), [Python AST](https://docs.python.org/3/library/ast.html).

The [review note](agent_instruction/what-has-to-be-done/2026-11-15-removal-check-review-and-plan.md) preserves the original findings and research citations. This revised master plan and the M1 handoff supersede its tentative choices.
