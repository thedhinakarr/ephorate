# Ephorate decisions

## 2026-11-15 — Accepted removal-check corrections

The owner accepted the review corrections and requested an updated plan plus a decision-complete M1 handoff, with no engine implementation. The current direction supersedes review-capacity simulation and earlier incident-risk scoring. The owner removed their working files; preserve those deletions and link [Git history](https://github.com/thedhinakarr/ephorate/tree/03448228bf6838f4cd7d9903e9bc73236e91afc8) rather than silently restoring obsolete artifacts.

**MIT.** The owner explicitly selected MIT. `LICENSE` uses the [standard MIT text](https://opensource.org/license/mit) and the existing Git author's name, Dhinakar R, with Ephorate contributors. This covers the project's own software and documentation, not third-party research in older Git history. PyPI availability remains unverified; local development needs no registration.

**Assertion evidence instead of JUnit inference.** A call-phase assertion is the supported witness; arbitrary runtime errors, missing tests and structural/setup/teardown failures are unjudged. The observer uses pytest hooks and structured fields because stock JUnit failure text does not supply a dependable typed-exception interface. Confirm an individual witness with repeat removal and a fresh head control. Failure of a control or integrity check cannot leave an unqualified held claim behind.

**Stable configured cohort.** M1 requires two passing head baselines with identical collection and stable outcomes. It does not silently ignore observed flakes. Stable skips/xfails are disclosed but cannot witness a removal. Missing, new, newly skipped/deselected or changed-outcome cases prevent clean-pass claims. Two runs establish observed stability only.

**Collective evidence remains collective.** One combined structural group is diagnostic. Neither collective failure nor collective success establishes each member's individual effect or a smallest group. Preserve unresolved members as unjudged and link the exact group evidence.

**Limited AST and idle claims.** Inert compares head with the exact single-unit reversal for eligible same-path regular modifications, with metadata/directive protections. Comparing only whole base/head ASTs could miss the effect of individually reverting one of two relocation hunks. It does not mean unrestricted semantic equivalence. New/deleted empty modules differ in existence. Idle means an added/modified test passed with changed subject units reverted; judges and other/configuration changes remained, and useful regression tests can be idle. Other tests may fail recognized assertions in that trial, but incomplete collection, structural/runtime/setup/teardown or integrity errors invalidate idle evidence. Requiring the entire suite to pass would miss idle tests whenever other tests correctly detect a removal.

**Independent clones and trusted tests.** Linked worktrees share administration, so M1 uses owned independent local clones with no shared objects, source locks/config changes, hooks or lazy network fetch. Unsupported checkout mechanisms fail explicitly. Dependencies exist beforehand; the same interpreter runs Ephorate and the supported pytest. Verify subject origins visible in the pytest process at observer checkpoints; this does not validate subprocess/native-extension loading or modules removed between checkpoints. Test code is trusted executable code, not an OS sandbox; later public replay needs isolated execution without secrets.

**Safety and evidence before optimization.** Serial full-suite trials, runtime/unit limits, process cleanup, changed-judge reporting, a versioned JSON schema and minimal fail-on belong in M1. Coverage selection, caching and parallelism wait for M3. Missing coverage contexts later fall back to full trials. Cache identity must include the test environment as well as source and command.

**Reports preserve the checked tree.** JSON defaults to stdout and human output to stderr; optional report files are outside the checked tree with no overwrite. Normal reports exclude raw test logs, locals, source contents and absolute scratch paths. The exact schema, reason codes, atomic-output behavior and exit handling are fixed in the M1 handoff.

**No engine implied by documentation.** M0 planning reconciliation is separable from website publication QA. Accessibility/browser/no-JavaScript checks remain required before the site is published. M1 can be explicitly assigned from its completed technical handoff without claiming those marketing checks ran. Do not add engine/package/CI artifacts during this planning session.

**Evidence gate remains M2.** Approve external repositories before cloning, disclose all selected failures/exclusions, audit individual rather than group-attributed witnesses, and report cost and uncertainty. The owner decides whether to continue. No claim of benefit, uniqueness, safety or speed is supported yet.

## 2026-11-15 — Milestone 1 implementation

The owner subsequently assigned M1 implementation explicitly. The earlier planning-only scope is historical; M2 replay, GitHub publishing and releases remain unassigned.

- Kept the prescribed standard-library runtime, frozen records, exact dependency pins, serial full-suite trials and report v1 contract. The observer's environment field is internal trial metadata; public trial records omit it and expose environment once at the report level.
- Git inspection rechecks effective filters and live/tree attributes before every source status, including final verification. Scratch and evidence directories select an outside parent before creation, ignoring an unsafe ambient temporary-directory location.
- Idle identity requires the qualified name and decorator-aware first source line. A callable whose code differs from its unwrapped function retains execution evidence but has unknown definition identity; `functools.wraps` cannot manufacture an idle result for another body.
- Unstable head controls clear earlier behavioral verdicts. Origin checks cover only expected modules visible at in-process checkpoints, including namespace parents; unimported modules do not get invented origin evidence.
- Output retains a validated directory descriptor, checks directory identity, writes an exclusive temporary file and publishes without overwrite. CLI finalization uses a separate POSIX deadline so a blocked stdout pipe cannot ignore the output allowance.
- Validation uses generated local repositories and isolated Python environments. CI is configured for both supported operating systems; only actual local results are recorded. No external replay or public performance claim follows fixture success.
