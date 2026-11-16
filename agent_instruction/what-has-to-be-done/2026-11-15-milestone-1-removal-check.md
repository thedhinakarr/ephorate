# Milestone 1: removal-check engine for OpenCode

Prepared 2026-11-15, then explicitly assigned and implemented the same day. **Status: implemented; observed checks are recorded separately.** See the [implementation record](../what-was-done/2026-11-15-milestone-1.md) and [validation record](../what-was-the-result/2026-11-15-milestone-1.md). The original assignment prompt and technical contract below are retained; their planning-only wording describes the earlier planning stage, not a new restriction on the later explicit implementation request.

## 1. Goal

Implement the smallest complete local Ephorate engine for trusted Python projects using pytest: inspect a committed change, revert individual units in independent scratch clones, execute the configured selected test suite, and report conservative evidence. Finish the fixtures, packaging and validation below, record actual results, and stop before M2.

Future implementation prompt:

> Implement only this Milestone 1 handoff. Read AGENTS.md, PROJECT_PLAN.md, agent_instruction/README.md and development-log.md first. Preserve the owner's documentation changes and intentional deletions. Work on implementation/removal-check-m1, reusing that branch if appropriate. Produce the package, generated fixtures and CI described here; run the acceptance checks; update actual work/results records, README status and decisions. Do not restore historical products, clone outside projects, publish, deploy, push or merge without a separate assignment. Stop after M1.

This document does not authorize executing that quoted prompt during planning.

## 2. Context

The owner selected the removal-check direction and MIT, after incident-risk and review-capacity directions. Old working files were intentionally deleted; history remains in Git. Do not execute the downloaded ZIP's stale archive/reset instructions. The implementation checkout can be dirty from the authorized reset and documentation work: inspect and preserve that state, rather than demanding a clean checkout or discarding it. The future tool's clean-input rule applies to its target repositories.

M0 planning and the M1 assignment are separate from remaining marketing/browser/publication checks. Those checks do not block the fixture engine. LICENSE is the owner-selected MIT text; preserve it.

The evidence claim is limited: a confirmed assertion demonstrates dependence of a test on one removal trial. A clean trial does not distinguish unnecessary code from necessary but untested code. AST equality is not unrestricted behavioral equivalence. Scratch clones are not a security sandbox. The engine executes trusted local tests; project code may use absolute paths, subprocesses or the network. Ephorate itself neither fetches dependencies nor calls remote services.

Supported M1 execution: POSIX Linux and macOS, CPython 3.11–3.15, Git >=2.49, and target pytest exactly 9.2.0 installed in the **same interpreter** running Ephorate. Only native synchronous pytest function/method items are supported. Windows, other interpreters, unittest.TestCase, doctest, asynchronous tests, subtests, custom collection protocols, xdist, retries, shell wrappers and dependency installation are unsupported. No coverage, parallel trials, cache, LLM, database, web service, Action, HTML report or second language.

## 3. Files likely involved

Create only the following implementation structure, plus the required existing documentation updates. These names are the chosen boundaries, not a request for a generic framework.

~~~text
.python-version
pyproject.toml
uv.lock
.github/workflows/ci.yml
src/ephorate/__init__.py
src/ephorate/__main__.py
src/ephorate/cli.py
src/ephorate/models.py
src/ephorate/git.py
src/ephorate/units.py
src/ephorate/engine.py
src/ephorate/report.py
src/ephorate/runners/__init__.py
src/ephorate/runners/pytest.py
src/ephorate/runners/bootstrap.py
src/ephorate/runners/observer.py
tests/
tests/fixtures/build.py
docs/report-v1.schema.json
~~~

Use ordinary frozen typed dataclasses, Literal aliases and small functions. No dependency injection container, abstract runner registry or persistence layer. All Git invocations belong in git.py; all runner subprocesses belong in runners/pytest.py. Bootstrap and observer are standalone shipped Python files, with no imports of the ephorate package inside the checked process.

At completion update README.md with actual installation/commands/limits, the engine status in README/index.html, docs/DECISIONS.md, agent_instruction/development-log.md, and dated what-was-done/what-was-the-result records. Do not mark the replay or publication work complete.

## 4. Required implementation behavior

### 4.1 Package, pins and CLI

Use distribution name ephorate, initial version 0.1.0a1, one real src-layout package, requires-python ">=3.11,<3.16", no runtime dependencies, and console entry point ephorate.cli:main. Support python -m ephorate identically. Obtain the installed version through importlib.metadata; do not supply an uninstalled-source fallback.

Pins: development Python 3.15.2; uv 0.13.8; build backend uv_build==0.13.8; pytest==9.2.0, ruff==0.17.5, mypy==2.4.1 in the development group. Include the standalone observer/bootstrap as wheel package files. Use Ruff defaults plus E, F, I, UP, B, line length 100, target py311; format with Ruff. Mypy strict=true, python_version="3.11", checking src/ephorate and tests. Use standard pytest discovery for the engine's tests, with no globally registered pytest11 entry point.

Metadata availability is verified; installation and compatibility are **not** claimed until M1 validation runs. The machine inspected during planning had uv 0.11.11, not the pinned version. Install/use the required development tooling during the explicit implementation assignment; never have the product install tooling in a checked project.

The CLI is:

~~~text
ephorate --help
ephorate --version
ephorate check [--repo PATH] [--base REF] [--source-root .|src]
  [--max-units INT] [--budget-seconds NUMBER]
  [--baseline-timeout-seconds NUMBER] [--min-trial-timeout-seconds NUMBER]
  [--timeout-factor NUMBER] [--fail-on loose,unjudged,idle]
  [--output PATH] -- pytest [PYTEST_ARGUMENTS...]
~~~

- No subcommand is a usage error, exit 2. Help exits 0. Version prints "ephorate 0.1.0a1" and exits 0.
- --repo defaults to current directory; resolve its Git top-level root. --base names the base commit itself, not a branch to merge-base implicitly.
- Accept either literal pytest, literal python/python3 followed by -m pytest, or the exact current interpreter path followed by -m pytest. Normalize all to the current sys.executable; never execute a supplied arbitrary executable or resolve a venv interpreter symlink to its base interpreter.
- Reject NUL arguments, shell pipelines/wrappers and absent test commands. Do not parse shell strings. Paths/selectors supplied to pytest must be relative to the checked root, contain no escaping ".." components, and resolve inside scratch. Reject explicit absolute configuration/output/plugin-path arguments. Builtin pytest options may use normal value arguments; reject an unknown positional argument if it cannot be a relative test path/node selector.
- Preserve intentional -k, -m and relative path/node selection. "Full suite" always means this configured selected cohort, not every test in the repository.
- Reject nonempty PYTEST_ADDOPTS, PYTEST_PLUGINS, PYTHONPATH and PYTHONHOME in the launching environment with a safe diagnostic asking the operator to use explicit arguments/tracked configuration. Never print their values.
- Reject effective collect-only/setup-only/interactive, maxfail/fail-fast, last-failed/failed-first/new-first/stepwise, distribution, loop-on-failure, repeat or rerun behavior, whether supplied by arguments or project addopts. Inspect the parsed pytest options in the observer, not only argument spellings. Reject loaded xdist, rerunfailures, flaky and repeat plugins in M1, even when their behavior is not selected.
- Keep ordinary pytest plugin autoload and tracked pytest configuration. Nonbuiltin implementations of pytest_collect_file, pytest_collect_directory, pytest_pycollect_makemodule or pytest_pycollect_makeitem are unsupported; report unsupported_collection rather than silently disabling them. Builtin _pytest plugins and this observer are allowed. Ordinary synchronous pytest fixtures, marks, assertion rewriting and stable collection_modifyitems selection remain supported. The observer rejects unittest.TestCase/doctest/custom item classes, async callables and subtest reporting with unsupported_collection; unittest setup/teardown assertions must never masquerade as pytest call-phase witnesses.
- pytest9.2.0 must be importable in the child interpreter. Any other version fails preflight; do not silently adapt. --version/help do not require pytest or Git.

Optional root .ephorate.toml contains one [check] table. Supported keys are test_command (nonempty array of strings), source_root ("." or "src"), judge_patterns and other_patterns (arrays of nonempty strings), max_units, budget_seconds, baseline_timeout_seconds, min_trial_timeout_seconds, timeout_factor, and fail_on (array from loose/unjudged/idle). No other keys/tables, strings standing in for arrays, bool-as-int, NaN, infinity, duplicate fail_on values or unknown verdicts.

Defaults: source_root=".", judge_patterns=[], other_patterns=[], max_units=50, budget_seconds=900, baseline_timeout_seconds=300, min_trial_timeout_seconds=30, timeout_factor=3, fail_on=[]. Test command has no implicit default. CLI values override corresponding TOML values; an explicit command after -- replaces test_command. --repo, --base and --output are CLI-only. An empty --fail-on is a usage error; omit it for no policy. Integers must be positive; other numeric limits must be finite and >0. Max units is an integer, not a float. No upper numeric bound is imposed; explicit larger values are the operator's choice. TOML is read from the target root, never the tool checkout.

Patterns use case-sensitive fnmatch.fnmatchcase against complete repository-relative POSIX paths; "*" can match "/". This is not gitignore syntax. Record normalized effective configuration, but never raw arbitrary pytest arguments: record a SHA-256 of their UTF-8 JSON encoding and safe invocation ["<python>","-m","pytest"] instead. No environment values enter reports.

### 4.2 Source Git boundary and scratch creation

All controlled Git processes use shell=False and an argument vector. Strip inherited GIT_* variables, then set GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_SYSTEM/GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM=1, GIT_OPTIONAL_LOCKS=0, GIT_NO_LAZY_FETCH=1, GIT_NO_REPLACE_OBJECTS=1, GIT_ALLOW_PROTOCOL=file, GIT_LITERAL_PATHSPECS=1, GIT_TERMINAL_PROMPT=0 and LC_ALL=C.

Every invocation supplies controlled -c values: core.hooksPath=<owned empty directory>, core.fsmonitor=false, core.attributesFile=os.devnull, core.autocrlf=false, core.eol=lf, gc.auto=0 and maintenance.auto=false. Do not print Git configuration values, stderr, source content or URLs on failure; report an operation name and stable reason.

Before source status, inspect effective local/worktree configuration and objects read-only. Reject bare, shallow, partial/promisor or sparse repositories, alternates, submodules, tracked symlinks, active clean/smudge/process filters, and skip-worktree/assume-unchanged index entries. Check both resolved trees, not only changed paths. For all tree paths, use check-attr --source=<SHA> -z --stdin for filter, working-tree-encoding and ident; active attributes are unsupported. Reject configured filter commands before running status because status itself can invoke clean filters. Do not modify configuration to make an input acceptable.

Read status --porcelain=v2 -z --untracked-files=all --ignore-submodules=none; require no staged, unstaged or nonignored untracked changes. Ignored dependency directories are permitted and are not copied. No stash, clean, reset, checkout, index refresh, refs creation, fetch or worktree creation in the original repository.

Resolve refs with rev-parse --verify --end-of-options <ref>^{commit}. Resolve HEAD first. Without --base, read locally stored symbolic refs/remotes/origin/HEAD, resolve it and run merge-base --all against HEAD; require exactly one result. Missing/ambiguous refs or objects are errors; never contact origin or infer main/master. Reject path names that are not valid UTF-8 or contain unsafe repository traversal; ordinary Unicode, spaces, leading dashes, tabs and newlines must work via -z and literal pathspecs.

For each baseline or trial create a new owned temporary directory outside the source root and Git metadata directories. Use:

~~~text
git clone --no-local --no-checkout --no-hardlinks --reject-shallow
  --template=<owned-empty-directory> -- <absolute-local-root> <owned-clone>
~~~

Use no --shared, --reference or linked worktree. Verify resolved base/head objects with cat-file -e in the clone; fail if a locally present but unreachable source object was not copied. Never create source refs or fetch missing commits to fix this. Verify the clone has no alternates/promisor configuration; remove its origin remote, then detach-checkout the resolved head SHA. All subsequent checkout/apply/index mutation is permitted only in that owned clone. Revalidate path ownership before deletion. Never reuse a dirty clone across executions.

Snapshot source HEAD, index bytes and refs plus tracked-file content digests during inspection; compare after processing without optional locks. If the source changes concurrently, stop with source_changed, never restore it, and do not claim source preservation. Tests prove unchanged nonignored/ignored sentinels too; the live comparison is not represented as an OS sandbox or proof against malicious test code.

### 4.3 File classification, units and precise reversal

Read raw changed-path metadata with rename detection disabled. Get per-path bytes using Git object IDs. Generate patches with:

~~~text
git diff --no-ext-diff --no-textconv --no-color --no-renames
  --diff-algorithm=myers --no-indent-heuristic --inter-hunk-context=0
  --full-index --binary -U0 <BASE> <HEAD> -- <literal-path>
~~~

Never parse filenames out of human diff headers. Use NUL-delimited metadata and retain patch bytes, including quoted headers and "No newline at end of file" markers. No external diff/textconv execution.

Judge priority is first, including when an exclusion overlaps. Protect:
- test/ and tests/ path components; basename test_*.py, *_test.py and conftest.py;
- pytest.toml, .pytest.toml, pytest.ini, .pytest.ini, pyproject.toml, tox.ini, setup.cfg and .ephorate.toml at any depth, plus .github/workflows/**;
- explicit judge_patterns;
- all base/head configured python_files patterns, conservatively unioned rather than recreating config precedence;
- Python ASTs containing test-prefixed functions, Test-prefixed classes or direct unittest.TestCase/TestCase bases;
- every local file reported by pytest_itemcollected before deselection, collection-skipped modules, conftest files and loaded local pytest plugins.

Read python_files from [pytest] in pytest.toml/.pytest.toml; [tool.pytest] and [tool.pytest.ini_options] in pyproject.toml; [pytest] in pytest.ini/.pytest.ini/tox.ini; [tool:pytest] in setup.cfg. Use tomllib/configparser without interpolation. TOML supports a string list or legacy whitespace-separated string; INI uses whitespace-separated patterns. Malformed declarations make classification fail with configuration_error, not a guessed subject. Judge files are never reversed. Report every changed judge path/status; renames appear as delete/add because rename detection is disabled.

Other priority comes next: other_patterns; path components migrations, generated, vendor, vendored; unsupported file types/languages and binary changes. Remaining regular .py files under source_root are subject candidates. A regular .py mode-only change or empty-file addition/deletion remains a subject unit with unjudged/unsupported_change and consumes the subject-unit cap; unsupported file types and binary changes are other. Other metadata-only changes receive synthetic other units. Files outside source_root are other with source_root_mismatch. Both baseline collections finalize judge classification before any reversal.

A deleted Python file not recognized as a judge is supported only under the verified ordinary pytest collection contract above and valid static base config. If its collection role remains ambiguous (custom/dynamic collector, unparsable base AST or unknown config), represent it as other/unjudged ambiguous_judge; never restore a possible test as a subject. This is conservative classification, not a claim to recognize arbitrary Python test frameworks.

For a same-path modified regular subject file with unchanged mode, one unit is one -U0 hunk. For a nonempty added/deleted subject file, one unit is the entire file patch and existence change. Empty additions/deletions, mode/type changes and binary patches are synthetic file units with unjudged unsupported_change; they never become inert. Other files receive one synthetic file unit, unjudged, retaining line counts when textual. Judges have zero removal units. A rename is explicitly two file changes; no inferred link or standalone rename reversion.

Unit IDs are lowercase SHA-256 hex of UTF-8 JSON with separators (",",":") over [1,path,kind,ordinal,base_blob_or_null,head_blob_or_null,sha256(patch_bytes)]. Synthetic patches use empty bytes. Ordinals are zero-based per file; order paths by UTF-8 bytes, then base/head range and ordinal. Kind is hunk, add_file, delete_file or file. Ranges are Git hunk start/count pairs, including zero-length anchors; whole-file ranges cover every line. Counts are additions/deletions without context. Never count removed judge lines as source units.

Before apply, verify the head blob/mode and exact hunk head slice. In fresh scratch use apply --reverse --index --unidiff-zero --check, then the same command without --check. Supply patch bytes on stdin. Never --3way, --reject, --unsafe-paths or --whitespace=fix. Independently construct expected resulting bytes by replacing the exact head slice with the base slice; verify final bytes/mode/existence and the changed-path allowlist. Offset/fuzz success alone is insufficient evidence. For multiple units in the same file, compose replacements in descending head-line order and verify the whole result. A failure yields patch_failed and no tests run for that trial.

Inert fast path: only admitted same-path regular .py hunk modifications with unchanged mode. Compare the entire head file against the exact head file with this one unit reversed, not the whole base file against head. Both resulting versions must parse under the running interpreter. Compare ast.dump(..., include_attributes=False), parsing with type_comments=True and retaining docstrings. A definition moved between separate hunks must be checked one hunk at a time; overall base/head equality cannot make either unit inert. Do not optimize or normalize away any AST node. Exclude edited first/second-line shebang/encoding comments and any changed comment token other than an empty comment or "#" followed by whitespace and plain prose characters (letters, digits, spaces, comma, full stop, apostrophe, hyphen). Any punctuation commonly used in directives, or case-insensitive words pragma, noqa, type, pylint, pyright, mypy, fmt, ruff, coverage, coding, encoding, doctest, is ineligible. This intentionally conservative rule is exact; excluded edits get normal trials, not an invented inert verdict. Record ast_equivalent, never "changes no behavior."

### 4.4 Runner process and observer evidence

The runner invokes [sys.executable,"-I","-B",absolute_bootstrap,private_manifest_path] in the fresh clone, with stdin/stdout/stderr=DEVNULL and start_new_session=True. The manifest and evidence files are owned mode-0600 temporary files outside the clone; no test output/traceback spool or debug-log mode exists in M1.

Bootstrap imports installed pytest before inserting project paths, verifies version 9.2.0, loads the standalone observer using importlib.util.spec_from_file_location under reserved name _ephorate_observer, then prepends the declared scratch source root and scratch root in that order and invokes pytest.main(args, plugins=[observer]). It imports no ephorate package. Reject a project module with the reserved observer name. Do not mutate test/conftest files or register a pytest11 entry point.

Map expected project module names from the union of regular base/head .py paths below source_root, converting identifier directory/stem components to dotted names and __init__.py to its package. Exclude known judges and other paths. A subject path that cannot map to a normal importable name is unjudged unsupported_module. Before collection, after collection, after each test, and at session finish, inspect sys.modules:
- any origin matching tracked base/head Python source/test paths in the original checkout is invalid; ignored .venv site-packages and the selected interpreter's standard library remain allowed for dependencies;
- an expected project name must resolve to its mapped scratch-relative file, or the corresponding scratch namespace paths; absence after deletion is allowed, fallback to an installed copy is not;
- namespace locations must all be in scratch; unknown/dynamic origins or collisions with already imported runner/stdlib modules are unsupported rather than guessed.
Use resolved paths and derive tracked modules only from Git trees, never a recursive scan of an ignored .venv. Expected project names must still resolve to scratch even if an installed copy lives in an otherwise allowed site-packages directory. Expected module identities refer to the baseline/head mapping, including deleted files; updates in a trial cannot erase the origin guard. Modules never imported by the selected suite need no fabricated origin event; this is compatible with loose evidence for unexecuted code. A fixture where observed subject imports escape scratch must fail, not return loose. Origin validation covers modules visible in the pytest process at the observer checkpoints; it does not establish where subprocesses/native extensions loaded code or detect modules removed between checkpoints.

Observer protocol version 1 is newline-delimited JSON, written by the child only. Maximum evidence is 16 MiB, maximum 100,000 selected cases, and each node ID/path/class-name string at most 16 KiB UTF-8. Limits produce evidence_limit; no truncated successful report. These are validation limits, not new CLI settings.

Protocol events, in order:
1. start: protocol=1, python_version, pytest_version, supported_options boolean and loaded plugin name/version pairs.
2. item: node_id, repository-relative path and nullable definition identity for every pytest_itemcollected before deselection.
3. collection: ordered selected node IDs, sorted deselected IDs, sorted observed judge files, sorted collection-skipped paths, collection_error boolean.
4. phase events: node_id, when (setup/call/teardown), outcome (passed/failed/skipped), was_xfail boolean, exception_category (none/assertion/structural/runtime/unknown), sorted fully qualified exception_types.
5. finish: pytest session exit code, origin_valid boolean, nullable error reason.

Use documented hooks: pytest_itemcollected, pytest_deselected, pytest_collectreport, pytest_collection_finish, pytest_runtest_makereport as a wrapper, pytest_runtest_logfinish and pytest_sessionfinish. Capture call.excinfo and the final TestReport after the inner makereport wrappers have completed; preserve an earlier exception graph too if present, so a wrapper cannot hide a structural cause. Read final xfail/outcome fields after inner wrappers, not before. Do not parse longrepr, assertion messages or JUnit. The protocol includes no source, messages, locals, captured output, credentials, absolute paths, PIDs or timestamps.

Assertion classification requires call-phase final failure and raw root exception isinstance(AssertionError, pytest.fail.Exception), with no xfail/XPASS status. Inspect both __cause__ and __context__ even when context is suppressed, plus BaseExceptionGroup members, using cycle detection, at most 64 nodes and depth 16. Structural means any instance/subclass of ImportError, ModuleNotFoundError, NameError, AttributeError, SyntaxError or IndentationError anywhere in that graph. A structural member overrides a wrapping assertion. A nonassertion cause/context, unknown/truncated graph or ExceptionGroup root is not a witness. Store only qualified class names/category. Setup/teardown failures never witness.

Require one start/collection/finish, no unknown event keys/types, no duplicate selected IDs or phase events, valid per-test phase ordering, matching subprocess/session exit codes, and complete evidence. A skipped/xfail setup legitimately has no call phase; every executed selected case still needs teardown. Exception: a complete start/collection/finish report with explicit collection_error may contain no phases because pytest aborted before running tests; this is structural_failure, never held/loose. This exception does not permit missing phases after any case execution has started, or a missing session marker. Nonbuiltin custom item protocols are unsupported. New subprocess exit codes, crash/no finish, invalid UTF-8/JSON, limits, incomplete phases and duplicate/rerun events fail closed.

### 4.5 Cohorts, verdicts, confirmation and idle tests

Run two fresh-head baselines. Both must exit 0, have the same ordered selected IDs, deselected set, collection-skipped paths, observed judge files and per-case phase/terminal outcomes, with at least one ordinary passed case. Collection errors or any failure invalidate the baseline. Stable skipped, xfailed and non-strict xpassed cases are disclosed and excluded from witnesses; strict XPASS is failure. These excluded cases must retain the same phase and terminal outcomes in every later trial. Do not call two observations proof of nonflakiness.

For ordinary baseline-passing cases, every trial must collect/select the same cases, execute setup/call/teardown, and preserve successful setup/teardown. Additional/missing/deselected cases, new skips/xfails/XPASS, changed excluded outcomes, unknown origin or incomplete execution override any assertion in that trial. Every requested pytest test selector is recorded only by the command hash; the report explicitly names the actual selected cases.

Reduction precedence:
1. interrupt, deadline or failed application;
2. invalid evidence/unsupported runner or origin;
3. explicit collection failure or structural exception (even when it also prevents collection of the normal cohort);
4. otherwise changed cohort/excluded outcomes;
5. setup/teardown failure or other runtime/unknown exception;
6. only then recognize complete ordinary-pass or assertion-only results.

A valid ordinary-pass trial has subprocess exit 0 and all required cases passing; verdict loose/full_suite_passed_without_unit. An assertion-only trial has exit 1, at least one required call assertion, all remaining required cases passed or assertion-failed, unchanged excluded cases and no higher-priority issue.

Assertion-only is a candidate, not immediately held. Repeat the same removal in a fresh clone, then execute a fresh unmodified-head control. Accept held/confirmed_assertion only when the first and repeat trials are valid assertion-only, their witness-node sets intersect, and the control exactly matches the baseline. Record the sorted intersection only; no need to repeat every witness individually.

A repeated removal that passes or changes the witness set to a disjoint set produces unjudged/confirmation_failed. Still run the head control when budget permits. Any **executed** head control that fails, times out, changes outcomes or is otherwise invalid aborts the check as unstable_control, invalidates all earlier held/loose unit verdicts to unjudged/unstable_control and clears their accepted witnesses. Retain trial observations and AST-only inert results. No later group/idle tests run. If budget prevents starting the control, only the current candidate is unjudged/budget_exhausted; earlier accepted findings remain. An ordinary interrupt uses interrupted status, not an invented instability diagnosis.

One diagnostic group is the sorted set of >=2 admitted units whose initial individual trials have structural_failure. If fewer than two, omit the group. Revert all its units and run once if possible. Store outcome and observed assertion nodes, with group id "structural-1"; never promote, clear or replace member verdicts based on collective pass/failure. No minimality claim or search. Runtime/setup errors without structural evidence do not join the group.

Identify added/modified test definitions from head-collected Python cases in changed judge files. Map callable qualified name and first line to a unique top-level function or class method AST definition, including decorators and end_lineno, in the head. A definition absent under the same qualified name in base is added; one present with different exact source bytes is modified. A pure positional shift with identical definition bytes is unchanged. Parametrized cases inherit their definition's change kind. Direct changes to fixture/config/module code remain judge changes; do not pretend every dependent test body was modified. Nested/generated/duplicate/ambiguous definitions or unparsable base source produce unknown mapping records. Deleted tests are judge changes, never idle candidates.

If candidates exist and every subject unit has a supported complete reversal admitted within the unit cap, run one fresh all-subject-reverted trial. Revert inert units too. Judges and other files remain at head. If any subject reversal is unsupported, cap-excluded or cannot apply, do not run a misleading subset: candidates become unknown. A complete idle trial may contain other tests' recognized call assertions; it need not pass globally. It must preserve the cohort/excluded outcomes and have no structural/runtime/setup/teardown/origin/evidence errors. An ordinary-baseline-passing candidate that itself passes is idle; an assertion-failing candidate is not_idle. Excluded baseline cases, absent/ambiguous candidates and all candidates in an invalid trial are unknown. A passing idle case can still be a useful regression test.

### 4.6 Budgets, termination and exit behavior

One job only. Start total monotonic budget before the first source Git read, including clones, controls and cleanup planning. Inspection Git commands have a 30-second ceiling; clones/checkouts have a 300-second ceiling; each is bounded by remaining total budget. Baselines use baseline_timeout_seconds, bounded by remaining budget. Later test timeout is max(min_trial_timeout_seconds, timeout_factor × slower successful baseline duration), bounded by remaining total budget.

max_units counts subject units in stable order, including potential inert units, whole-file units and subject units later judged unsupported; synthetic other units do not consume it. Classify all changed files and report all units. Only the first max_units subject units are admitted. The rest are unjudged/unit_cap even when they might be AST-equivalent. No idle trial when a subject unit is excluded. Group/idle trials and controls consume time but not extra unit slots.

When time expires, stop scheduling; pending units are unjudged/budget_exhausted. If a running non-control trial times out, its unit is unjudged/timeout, and continue only when total time remains. A budget-limited but valid check is partial, not an infrastructure error. It can exit 0 or 1 according to fail_on. No hidden retries.

POSIX process handling: start a new session, retain owned PGID, on timeout/SIGINT/SIGTERM send SIGTERM to that group, wait up to 2 seconds, then SIGKILL if needed and reap before cleanup. A project daemon escaping the group is outside the trusted-test boundary. Only delete paths created and recorded as owned by this invocation; no broad temp scan or git worktree prune. Cleanup may overrun the analysis budget to terminate/reap safely. After child termination, give final source verification a separate 30-second deadline, and output/owned-file cleanup a further 30-second finalization allowance; these do not schedule more tests. This ensures an exhausted analysis budget still permits source verification and an honest partial report. A failed verification/finalization is infrastructure_failure, not successful partial completion.

- Exit 0: complete/partial report with no requested fail_on match.
- Exit 1: complete/partial report matching any requested loose/unjudged/idle condition. idle matches only positive idle records.
- Exit 2: usage/preflight/configuration/baseline/infrastructure/source-change/output failure; never also 1.
- Exit 130/143: caught SIGINT/SIGTERM after cleanup. Emit an interrupted report when Change exists; before it exists, stderr diagnostic only.
- A second signal requests prompt termination after best-effort child kill; do not promise cleanup after SIGKILL/power loss.

Before Change exists, errors emit only safe stderr text. Afterwards emit a failed/interrupted diagnostic report with pending units unjudged/run_aborted and no fabricated completion. Non-baseline trial parse/protocol errors are conservative unjudged findings; inability to start the runner, failed clone or tool I/O is infrastructure failure and aborts. Preserve already valid findings in an infrastructure partial report, but run.status=failed and exit 2; unstable_control is the specific case that invalidates earlier behavioral findings.

### 4.7 Exact records, module APIs and report v1

Use these internal frozen records; tuples are immutable, Path/bytes stay internal, and no record carries raw runner output. Enumerated strings below are the complete M1 values.

~~~text
FileClass = judge | subject | other
UnitKind = hunk | add_file | delete_file | file
Verdict = held | loose | inert | unjudged
Outcome = passed | failed | skipped | xfailed | xpassed | unknown
Phase = setup | call | teardown
ExceptionCategory = none | assertion | structural | runtime | unknown
TrialPurpose = baseline | single | repeat | control | group | idle
TrialStatus = passed | assertion_failure | structural_failure | runtime_failure |
  phase_failure | cohort_mismatch | origin_violation | invalid_evidence |
  runner_failure | timeout | budget_exhausted | interrupted | patch_failed
RunStatus = complete | partial | failed | interrupted
IdleStatus = idle | not_idle | unknown
ChangeKind = added | modified | unknown
~~~

Reason is one of:
confirmed_assertion, full_suite_passed_without_unit, ast_equivalent,
judge_protected, unsupported_file, excluded_pattern, source_root_mismatch,
unsupported_change, unsupported_module, ambiguous_judge, patch_failed,
structural_failure, runtime_failure, phase_failure, cohort_mismatch,
origin_violation, invalid_evidence, evidence_limit, unsupported_collection,
unsupported_runner, runner_failure, timeout, budget_exhausted, unit_cap,
confirmation_failed, unstable_control, baseline_failed, baseline_unstable,
no_tests, configuration_error, unsafe_repository, missing_ref, missing_object,
source_changed, infrastructure_failure, output_error, interrupted, run_aborted,
mapping_ambiguous, no_passing_baseline, unsupported_subject_reversal,
passed_without_subject_changes, assertion_without_subject_changes.
No free-text reason masquerading as an enum; descriptive CLI text is separate and sanitized.

~~~text
CheckConfig(repo:Path, base_ref:str|None, source_root:str,
  pytest_argv:tuple[str,...], judge_patterns:tuple[str,...],
  other_patterns:tuple[str,...], max_units:int, budget_seconds:float,
  baseline_timeout_seconds:float, min_trial_timeout_seconds:float,
  timeout_factor:float, fail_on:tuple[str,...], output:Path|None)

FileChange(path:str, status:str, base_blob:str|None, head_blob:str|None,
  base_mode:str|None, head_mode:str|None, classification:FileClass,
  reason:Reason|None, additions:int|None, deletions:int|None)

SourceState(head_sha:str, index_sha256:str,
  refs:tuple[tuple[str,str],...], tracked_files:tuple[tuple[str,str],...])

Change(repo:Path, git_dir:Path, common_dir:Path, base_sha:str, head_sha:str,
  base_tree:str, head_tree:str, files:tuple[FileChange,...], source_state:SourceState)

Unit(id:str, path:str, kind:UnitKind, ordinal:int, base_start:int,
  base_count:int, head_start:int, head_count:int, additions:int|None,
  deletions:int|None, patch:bytes, classification:FileClass)

PhaseResult(when:Phase, outcome:str, was_xfail:bool,
  exception_category:ExceptionCategory, exception_types:tuple[str,...])

CaseResult(node_id:str, path:str, definition_name:str|None,
  definition_start:int|None, definition_end:int|None, outcome:Outcome,
  phases:tuple[PhaseResult,...])

Collection(selected:tuple[str,...], deselected:tuple[str,...],
  judge_files:tuple[str,...], skipped_paths:tuple[str,...], error:bool)

TrialResult(id:str, purpose:TrialPurpose, unit_ids:tuple[str,...],
  status:TrialStatus, reason:Reason|None, exit_code:int|None,
  collection:Collection|None, cases:tuple[CaseResult,...], duration_s:float)

UnitResult(unit:Unit, verdict:Verdict, reason:Reason,
  witnesses:tuple[str,...], trial_ids:tuple[str,...], group_ids:tuple[str,...])

GroupResult(id:str, unit_ids:tuple[str,...], trial_id:str,
  status:TrialStatus, assertion_nodes:tuple[str,...])

IdleResult(node_id:str, path:str, change:ChangeKind, status:IdleStatus,
  reason:Reason, trial_id:str|None)

Baseline(trial_ids:tuple[str,...], passing:tuple[str,...],
  excluded:tuple[tuple[str,Outcome],...])

CheckReport(change:Change, config:CheckConfig, status:RunStatus,
  reason:Reason|None, baseline:Baseline, units:tuple[UnitResult,...],
  trials:tuple[TrialResult,...], groups:tuple[GroupResult,...],
  idle_tests:tuple[IdleResult,...], environment:Environment,
  total_duration_s:float)
~~~

Environment contains python_version, implementation ("cpython"), platform ("linux"/"macos"), git_version (string|null), pytest_version (string|null) and plugins (null|sorted pairs of name/version, with each version nullable for local plugins). Unobserved Git/pytest/plugin metadata is null in early failed reports, never a fabricated installed version. Successful baseline reports require observed non-null Git/pytest metadata and a plugin list. Never store absolute plugin origins. File status is exactly A, D, M or T; unknown statuses fail inspection. phase outcome is passed/failed/skipped only. Configuration string aliases above become Literal types, not unconstrained runtime values.

Module functions:

~~~text
cli.main(argv:Sequence[str]|None=None) -> int
git.resolve_change(repo:Path, base:str|None, deadline:float) -> Change
git.snapshot(change:Change, deadline:float) -> ContextManager[Path]
git.patch_for_path(change:Change, path:str, deadline:float) -> bytes
git.apply_units(root:Path, change:Change, units:Sequence[Unit], deadline:float) -> None
git.verify_source_unchanged(change:Change, deadline:float) -> None
units.split_change(change:Change, config:CheckConfig, deadline:float) -> tuple[Unit,...]
units.is_inert(change:Change, unit:Unit, deadline:float) -> bool
runners.pytest.run_trial(root:Path, change:Change, config:CheckConfig,
  trial_id:str, purpose:TrialPurpose, unit_ids:tuple[str,...],
  timeout_s:float) -> TrialResult
engine.check(change:Change, config:CheckConfig, deadline:float) -> CheckReport
report.as_dict(report:CheckReport) -> dict[str,object]
report.write_json(report:CheckReport, stream:TextIO) -> None
report.write_exclusive(report:CheckReport, destination:Path) -> None
~~~

A small EphorateError(reason:Reason, operation:str) is the sole expected-boundary exception; neither its message nor traceback includes backend stderr/config/test text. KeyboardInterrupt and termination handling stay distinct. Internal helpers may be private functions; do not expose new product APIs. SourceState is private verification data held by Change; it is never serialized. Ref pairs are refname/object ID; tracked-file pairs are path/content SHA-256. Do not use a global registry for per-check state.

The public JSON schema is exactly the following, with every named key required and additionalProperties=false at each fixed-shape object. The sole dynamic dictionary is timings.trials: its keys are existing trial IDs and its values are finite nonnegative seconds; no unreferenced IDs are permitted. Nullability is only as specified in the records. Tuples become arrays. Write a matching Draft 2020-12 docs/report-v1.schema.json; schemas are documentation, not a runtime dependency.

~~~text
{
  schema_version: 1,
  tool: {name:"ephorate", version:"0.1.0a1"},
  environment: {python_version, implementation, platform, git_version:null|string,
                pytest_version:null|string, plugins:null|[{name,version:null|string}]},
  change: {base_sha, head_sha, base_tree, head_tree,
           files:[FileChange fields exactly]},
  config: {source_root, judge_patterns, other_patterns, max_units,
           budget_seconds, baseline_timeout_seconds,
           min_trial_timeout_seconds, timeout_factor, fail_on,
           invocation:["<python>","-m","pytest"], command_sha256,
           effective_config_sha256},
  status: RunStatus,
  reason: null|Reason,
  baseline: {trial_ids, passing, excluded:[{node_id,outcome}]},
  units: [{
    id,path,kind,ordinal,base_start,base_count,head_start,head_count,
    additions,deletions,classification,verdict,reason,witnesses,trial_ids,group_ids
  }],
  trials: [{
    id,purpose,unit_ids,status,reason,exit_code,
    collection:null|{selected,deselected,judge_files,skipped_paths,error},
    cases:[{node_id,path,definition_name,definition_start,definition_end,
            outcome,phases:[{when,outcome,was_xfail,
                            exception_category,exception_types}]}]
  }],
  groups:[{id,unit_ids,trial_id,status,assertion_nodes}],
  idle_tests:[{node_id,path,change,status,reason,trial_id}],
  reading_list:{unit_ids,group_ids,idle_node_ids,judge_paths},
  counts:{units:{held,loose,inert,unjudged},
          subject_lines:{held,loose,inert,unjudged},
          unknown_line_unit_ids},
  timings:{total_s, trials:{<trial_id>:seconds}}
}
~~~

All counts are nonnegative integers. Unknown binary line counts are null; do not treat them as zero measured lines. subject_lines adds known additions+deletions only for subject units of each verdict and lists unknown IDs separately. Reading list includes loose/unjudged unit IDs, every group ID, only positive idle node IDs, and all changed judge paths. Every file and unit appears once; cross-references must exist. Status partial means cap/budget left units/idle unfinished, not merely that an ordinary unit is unjudged. No duration appears outside timings.

Baseline trial IDs are baseline-1/-2; individual IDs are unit-<full-id>-1/-2 and control-<full-id>; group trial is group-structural-1; idle trial is idle-all. Do not expose scratch paths, random run IDs, timestamps, source/patch bytes, refs before resolution, raw argv or environment values. Stable ordering plus json.dumps(sort_keys=True, ensure_ascii=True, allow_nan=False) and a trailing newline is required. Sort unordered sets lexically; retain actual selected/phase execution order. Hash normalized semantic config excluding repo/output/command secrets; include command_sha256. Report typed plugin names/versions, not plugin configuration.

Default: serialize once after completion to stdout; concise summary and safe diagnostics go to stderr. With --output, stdout stays empty and only the file receives JSON. Validate destination before running: parent exists, resolves outside source root/git-dir/common-dir, final basename is nonempty and does not exist, including dangling symlinks. Open/retain the parent directory fd; create an exclusive mode-0600 sibling temp, write/flush/fsync, then os.link temp to the destination using dir_fds and no following symlinks. Link failure if destination now exists is output_error; never overwrite. Unlink the owned temp in finally and fsync the directory where supported. No incomplete destination is published. Stdout is prepared in memory first but cannot promise filesystem-style atomicity to a pipe; broken pipe is exit 2 without a traceback.

## 5. Edge cases and failure modes

These fixture expectations are mandatory. Build each as an isolated local Git repository with fixed author identity/dates and two commits; no external clone, vendored project or network. Fixture data uses synthetic code only. tests/fixtures/build.py exposes --case NAME --dest EMPTY_PATH, prints only resolved base/head SHAs as JSON, and refuses a nonempty destination. A fixture can use multiple intentional hunks/files; assert each unit, not just aggregate counts.

| Fixture | Exact essential expectation |
|---|---|
| needed_assertion | Change return 1 to 2; assert ==2: held, same witness in repeat, passing control; three unit-related runs |
| untested_needed | Tested module with changed unexercised function: loose, with no necessity claim |
| unneeded_branch | Dead added branch: loose |
| prose_comment | Eligible comment-only modified existing file: inert, zero individual runs |
| directive_comment | Changed "# pragma: no cover" or type comment: never inert; ordinary trial result |
| moved_definition | Definition relocation in separate deletion/addition hunks: compare each head-minus-unit AST; no inert inference from overall base/head equality |
| metadata_subject | Regular .py mode-only change and empty-file add/delete: subject/unjudged unsupported_change, consume cap; binary/type changes remain other |
| runtime_exception | Removal raises ValueError without assertion: unjudged/runtime_failure |
| structural_exception | Removal raises NameError: unjudged/structural_failure |
| wrapped_structural | AssertionError/pytest.fail wraps ImportError, including from None: unjudged/structural_failure |
| setup_teardown | Failure in either phase: unjudged/phase_failure; no held even if another case asserts |
| cohort_drift | Removal adds/removes/deselects a case or introduces skip/xfail: unjudged/cohort_mismatch |
| stable_exclusions | Stable skip, xfail and non-strict xpass remain disclosed; ordinary passing case can witness; changing exclusion => cohort_mismatch |
| no_tests | Empty or fully deselected suite: failed baseline, exit 2, no held/loose |
| all_skipped | No ordinary pass: failed baseline, exit 2 |
| flaky_baseline | Two fresh head runs differ: baseline_unstable, exit 2, no exclusion workaround |
| flaky_confirmation | Candidate assertion not repeated: unjudged/confirmation_failed |
| unstable_control | Executed head control differs: failed/unstable_control; earlier held/loose cleared |
| group_only | Two structural units jointly assert or pass: individual units stay unjudged; group observation records outcome |
| added_module | New nonempty module removal includes absence; import failure => structural_failure, never empty-file approximation |
| deleted_module | Revert supported deleted source file with base bytes/existence; clean test suite => loose |
| empty_file | New/deleted empty module: unjudged/unsupported_change, never inert |
| pure_deletion_hunk | Restore deleted lines in existing source; exact base slice and resulting verdict checked |
| rename_pair | No-renames produces delete/add; each record visible, no inferred individual held from a group |
| judge_overlap | Test matched by both subject/exclusion patterns: judge, no reversed trial |
| custom_test_names | Base/head python_files differ; deleted custom test remains judge; ambiguous deleted dynamic test is unjudged |
| config_change | pytest.toml/.pytest.toml/pyproject/conftest/workflow changes protected, reported, never reversed |
| idle_added_modified | Added and edited test definitions pass after all subjects reverted: idle; meaningful regression test is still not called useless |
| idle_mixed | One candidate passes while another test has recognized assertion: positive idle evidence permitted |
| idle_bad_run | Structural/error/missing cohort in all-subject trial: all candidates unknown |
| idle_ambiguous | Dynamic/duplicate definition mapping: unknown, never idle |
| cap | 51 subject units at cap50: last unjudged/unit_cap, status partial, no idle subset trial |
| budget | Deadline reached: remaining units unjudged/budget_exhausted; no false failed baseline when baseline had already succeeded |
| timeout | Infinite-loop trial/child: unjudged/timeout; group killed/reaped, source unchanged |
| interrupt | SIGINT/SIGTERM during child: 130/143, interrupted report, no owned running child after cleanup |
| source_unchanged | Success, error, timeout, interrupt preserve original tracked/untracked/ignored sentinel bytes, index and refs |
| git_rejections | Dirty/partial/shallow/alternates/filters/symlinks/submodules/sparse/index flags fail without executing filters/hooks |
| literal_paths | Space, Unicode, leading "-", tab/newline, CRLF and missing EOF newline round-trip correctly |
| malformed_evidence | Missing/duplicate/oversized/malformed events or wrong exit code => unjudged/invalid_evidence (evidence_limit for limit) |
| wrong_import | Editable/installed fallback to original/outside module is rejected; never loose |
| local_venv | Interpreter and dependencies inside ignored target/.venv are permitted; original tracked subject imports are still rejected |
| unsupported_items | unittest setup/teardown assertions, doctest/custom items, async tests and subtests fail baseline with unsupported_collection, never held |
| package_named_ephorate | Checked project named ephorate imports its scratch package, not the observer/tool package |
| output_safety | Existing file/dangling symlink/inside-repo path/race => no overwrite, exit2; successful file output has empty stdout |
| deterministic | Same fixtures/input/environment twice: reports identical after removing timings |
| fail_on | Complete loose/unjudged/idle matching requested condition =>1; otherwise0; infrastructure2 overrides policy |

Tests of budgets/signals may use controlled clocks and tiny explicit timeouts; do not make the normal suite wait minutes. At least one real subprocess/process-group test must prove child termination on each supported OS. Source-preservation tests compare bytes/refs, not only git status. A test failure expected by Ephorate is not a failure of Ephorate's own pytest suite.

## 6. Test/validation commands

During the explicit implementation assignment, pin tooling, create the lockfile and run:

~~~sh
uv --version
uv sync --locked
uv run --locked ruff check src/ephorate tests
uv run --locked ruff format --check src/ephorate tests
uv run --locked mypy src/ephorate tests
uv run --locked pytest
uv build --no-sources
uv run --locked ephorate --help
uv run --locked python -m ephorate --version
git diff --check
~~~

The first lock generation uses pinned uv 0.13.8; subsequent installs/checks use --locked. Do not run uv sync --locked before a lockfile exists and describe that failure as validation. No broad formatter changes outside the new Python files.

Installed-wheel smoke test must run outside the source checkout. These commands are for the future implementation, with the stated builder interface; paths are task-specific variables, never HOME:

~~~sh
repo_root="$(pwd)"
smoke_root="$(mktemp -d)"
uv run --locked python tests/fixtures/build.py --case needed_assertion --dest "$smoke_root/target"
uv venv --python 3.15.2 "$smoke_root/venv"
uv pip install --python "$smoke_root/venv/bin/python" "$repo_root/dist/ephorate-0.1.0a1-py3-none-any.whl" pytest==9.2.0
cd "$smoke_root"
"$smoke_root/venv/bin/ephorate" --help
"$smoke_root/venv/bin/python" -m ephorate --version
"$smoke_root/venv/bin/ephorate" check --repo "$smoke_root/target" --base HEAD^ -- pytest -q > "$smoke_root/result.json"
"$smoke_root/venv/bin/python" -c 'import json; r=json.load(open("result.json")); assert r["status"]=="complete"; assert r["counts"]["units"]["held"]==1'
cd "$repo_root"
~~~

Use the exact wheel filename/version above; verify it exists. Also repeat installed-wheel execution against package_named_ephorate, and from a fresh checkout/environment to catch undeclared source dependencies. Package installation may use the public package index during development/CI; fixture checks themselves must require no network. Remove only the specifically created smoke directory after checks, using the test harness's owned-directory cleanup.

CI: GitHub Actions on push/pull_request, permissions contents:read, no service containers, no application secrets/token passed to tests. Matrix ubuntu-latest and macos-latest × Python 3.11, 3.12, 3.13, 3.14, 3.15, fail-fast false. Full lint/format/mypy on Linux 3.15 only; locked tests, build and installed-wheel smoke on every matrix entry. Set checkout persist-credentials:false. Pin actions by full commits:
- actions/checkout v7.0.1: 3d3c42e5aac5ba805825da76410c181273ba90b1
- astral-sh/setup-uv v10.3.3: 68559e99cc807c1eb7e9238fd43a15bba460eec2; version 0.13.8.

Use uv's requested matrix interpreter for each environment; .python-version remains development3.15.2. CI fixture Git operations are local only. Do not claim remote CI passed unless an authorized run was actually observed; if pushing is not authorized, validate locally and report that CI execution remains unobserved.

Primary sources behind these choices: [Python support](https://devguide.python.org/versions/), [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/), [pytest9 configuration](https://docs.pytest.org/en/stable/reference/customize.html), [pytest hooks](https://docs.pytest.org/en/stable/reference/reference.html), [pytest exit codes](https://docs.pytest.org/en/stable/reference/exit-codes.html), [exception chaining](https://docs.python.org/3/library/exceptions.html), [Git clone](https://git-scm.com/docs/git-clone), [Git diff](https://git-scm.com/docs/git-diff), [Git apply](https://git-scm.com/docs/git-apply), [Git attributes](https://git-scm.com/docs/gitattributes), [checkout release](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-uv release](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.3).

## 7. Acceptance criteria

- The installed console command and python -m entry point implement precisely this CLI and schema; no command described as working is missing.
- All fixture expectations pass, including assertion wrapping, source-origin guards, unchanged excluded outcomes and globally invalidated behavioral verdicts after a failed head control.
- Judge files never enter a reversal, no group outcome is promoted to a member, and no partial subject-reversion trial is called an idle check.
- Scratch clones have independent object storage and no source-linked refs/hooks/remotes. Reversal bytes/existence and source preservation are tested across success/failure/interrupt. Import-origin acceptance covers modules observed in the pytest process at the specified checkpoints; it makes no claim about subprocess/native-extension loading or modules removed between checkpoints.
- Baselines, cohort completeness, repeat/control evidence, budgets and interrupt exit codes have observed tests; no false success on missing/malformed evidence.
- JSON contains exact enums/keys/provenance, no raw outputs or secrets, stable deterministic semantics, and safe exclusive publication.
- Locked lint/format/type/tests/build and installed-wheel checks pass on tested platforms/interpreters. Record any matrix entries not actually run; do not mark full matrix validation complete without evidence.
- README accurately explains target pytest/interpreter restrictions, selected-cohort meaning, source-root/import policy, trusted-test boundary, runtime limits and each verdict. MIT stays intact.
- Actual work/results/log entries name commands and outcomes, unresolved limitations and the next M2 owner gate. No external replay, publish, push, merge or deployment occurs by implication.

## 8. Explicit assumptions

- This is a decision-complete future implementation contract, not permission to implement during the current planning request.
- The owner explicitly chose MIT. Third-party papers and historical ZIP assets are not relicensed by that choice.
- M1 deliberately supports a constrained pytest execution model. Broader pytest versions, custom collectors, source layouts, filters, Windows and dependency orchestration require a later reviewed change, not silent fallback.
- Two baselines plus witness/control repetition reduce observed uncertainty; they cannot eliminate nondeterminism, hidden dependencies or weak assertions.
- Ordinary comment AST equivalence remains limited evidence. No claim of correctness, unnecessary code, safe deletion or merge approval follows any verdict.
- Tool actions preserve the checked repository; arbitrary trusted tests are not isolated from the user's machine. M2 needs owner-approved repositories and separate disposable execution isolation.
- If verified tool behavior contradicts an exact assumption, stop that implementation path, document the observed conflict and propose the smallest correction. Do not weaken verdicts, change pins silently or claim unrun checks passed.
