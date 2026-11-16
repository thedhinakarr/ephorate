# Ephorate

**Every changed line answers to a test, or to you.**

Ephorate is a local tool that reverts a code change one piece at a time in a temporary clone and reruns your tests. It records reproduced assertion witnesses and removals the test suite did not detect. Coding agents use that evidence to investigate or test a change before asking for review. Reviewers use it to see where to start reading.

Repository: [thedhinakarr/ephorate](https://github.com/thedhinakarr/ephorate)

> **Status:** Milestone 1 is implemented and validated on generated local fixtures. This is an unpublished alpha, not evidence of usefulness on real PRs. See the [implementation record](agent_instruction/what-was-done/2026-11-15-milestone-1.md) and [observed validation](agent_instruction/what-was-the-result/2026-11-15-milestone-1.md). Milestone 2 still needs owner-approved repositories.

The owner has selected the [MIT license](LICENSE).

## Run locally

Development requires uv **0.13.8**, Git **2.49+** and a POSIX macOS/Linux host. The development interpreter is pinned to CPython **3.15.2**. The package supports CPython 3.11–3.15 and requires **pytest 9.2.0 in the same interpreter** for checked tests. Ephorate does not install a target project's dependencies.

```sh
uv sync --locked
uv run --locked ephorate --help
uv run --locked python -m ephorate --version

fixture_root="$(mktemp -d)"
uv run --locked python tests/fixtures/build.py --case needed_assertion --dest "$fixture_root"
uv run --locked ephorate check --repo "$fixture_root" --base HEAD^ -- pytest -q
```

If the system uv is older, prefix these uv commands with `uv tool run --from uv==0.13.8`, for example `uv tool run --from uv==0.13.8 uv sync --locked`.

For a real trusted target, install the built wheel into its existing test environment (`uv build --no-sources` creates `dist/ephorate-0.1.0a1-py3-none-any.whl`). Then run that environment's `python -m ephorate check --repo /path/to/target --base HEAD^ -- pytest -q`. Staged, unstaged and nonignored untracked changes are rejected. Explicit `--base` is compared directly with committed HEAD; without it, Ephorate uses the merge base with locally available `origin/HEAD` and never fetches.

Use `--source-root src` for a `src/` layout; the default is `.`. This choice defines the project module names guarded during imports. Tests/plugins must already work with that environment and scratch layout. Shell wrappers, unittest/doctest, async/subtests, custom collectors, distributed/retry plugins, partial/shallow repositories, submodules, symlinks and checkout filters are unsupported. Ambient `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`, `PYTHONPATH` and `PYTHONHOME` must be empty; use explicit arguments and tracked configuration instead.

JSON goes to stdout and a compact summary to stderr. `--output /outside/target/report.json` publishes a new file exclusively, never overwriting an existing file or writing inside the checked repository. The [report v1 schema](docs/report-v1.schema.json) includes changed judges, baseline/trial evidence, reasons, witnesses, groups and idle observations. Raw test output is discarded.

Optional `.ephorate.toml` at the target root:

```toml
[check]
test_command = ["pytest", "-q"]
source_root = "src"
max_units = 50
budget_seconds = 900
baseline_timeout_seconds = 300
min_trial_timeout_seconds = 30
timeout_factor = 3
judge_patterns = []
other_patterns = []
fail_on = ["loose", "unjudged"]
```

CLI values override TOML; a command after `--` replaces `test_command`. Patterns use case-sensitive `fnmatch` against the whole POSIX relative path, where `*` can match `/`. Unknown keys and malformed values fail. The complete interface is in the [M1 contract](agent_instruction/what-has-to-be-done/2026-11-15-milestone-1-removal-check.md).

Default limits are 50 subject units and 900 seconds of analysis, with two baselines limited to 300 seconds each. Later trial timeouts are the greater of 30 seconds or three times the slower baseline, capped by remaining time. Source verification and final output each get a separate 30 seconds. Exhausted limits produce explicit partial/unjudged results. Exit codes: `0` complete/partial without a policy match; `1` a requested `--fail-on loose,unjudged,idle` match; `2` invalid input, baseline or infrastructure failure; `130`/`143` interrupt/termination. A zero exit code is not merge approval.

Developer checks: `uv run --locked ruff check src/ephorate tests`, `uv run --locked ruff format --check src/ephorate tests`, `uv run --locked mypy src/ephorate tests`, `uv run --locked pytest`, and `uv build --no-sources`.

## Why

Coding agents write code faster than people can review it. A 2026 study of 655 firms estimated that after firms adopted coding agents, pull requests opened rose about 36% and review time from submission to merge rose about 56%, while resolved issues rose about 14% (that last estimate is marginally insignificant). Reviewers are reading more pull requests for each finished piece of work.

Two things make an agent's pull request slow to read:

- **Extra code.** Agents keep changes the task did not need: leftovers from trial and error, defensive branches, unrequested cleanups.
- **Tests that prove little.** The agent writes the tests as well as the code, so "all tests pass" says less than it used to.

A diff alone does not show which behavior the tests detect. Ephorate will investigate that with one question per piece of the change: *which assertion fails if this is removed?* A passing removal trial cannot distinguish unnecessary code from necessary code that the tests miss.

## How it works

1. **Split the change.** Modified source files use diff-hunk units; new and deleted source files use whole-file reversions, including file existence. Changed test files are not split; they are the judges.
2. **Check the baseline.** The test command runs twice on the full change. Both runs must pass consistently. A failure, changed outcome or changed test collection stops the check; flaky tests are not ignored.
3. **Remove one unit and run the tests.** Each trial uses an independent temporary clone and configured resource limits. A possible assertion witness is checked in repeated removal trials with passing head controls.
4. **Give each unit a verdict.**

| Verdict | Meaning |
|---|---|
| `held` | An individual unit's removal produces an explicit assertion witness, reproduced on removal with a fresh passing head control. The report names the witness; it does not establish dependence on every line in the unit. |
| `loose` | A valid removal trial passes: the tests found no witness. This does not establish that the removed code is unnecessary. |
| `inert` | The file has the same syntax tree under the configured comparison with or without the unit. This is not proof of unchanged behavior. |
| `unjudged` | Evidence is insufficient: an unsupported file, structural failure, unstable result, timeout or exhausted budget. |

5. **Report.** A terminal summary, a JSON file for agents and CI, and later a comment on the pull request.

M1 may run one combined diagnostic trial for structurally failing units. Its collective outcome is a separate group observation, not a confirmed `held` verdict. It never promotes members from their individual `unjudged` verdicts.

Ephorate also runs an all-subject-reverted trial when its reversals and budget permit, retaining judge files and other files at the head version. An added or modified test that passes in this valid trial is reported as **idle**: no dependence on the reverted subject changes was observed in that run. This is not independence from the whole change. An invalid trial provides no idle verdict. Wrapped or dynamically ambiguous callable identities remain unknown.

## What it looks like

Illustrative reading-list layout, not actual CLI output. The current CLI emits JSON and a compact stderr summary:

```text
$ ephorate check --base origin/main -- pytest -q

Change    6 units, 22 changed lines in 4 files
Baseline  214 tests passed, 2 stable head runs

held      2 units    8 lines   repeated assertion witnesses
inert     1 unit     3 lines   same syntax tree
loose     2 units    9 lines   every test passes without them
unjudged  1 unit     2 lines   not code

Read these first
  loose     billing/refund.py:88-90   all 214 tests pass without it
  loose     billing/retry.py:12-17    all 214 tests pass without it
  unjudged  settings.toml:4           not code
```

The agent workflow is to run `ephorate check` before opening a pull request, investigate each `loose` unit, and either justify deleting it or add a meaningful test that detects its removal. Never weaken an existing test to change a verdict.

## What Ephorate does not do

- **It does not edit the checkout it checks.** It reports; a person or an agent decides what to delete. Tests run in independent temporary clones. These are not sandboxes: test commands and plugins must be trusted and can affect external files, processes or services.
- **It does not use a language model.** Classification follows recorded evidence. Flaky tests, changing environments and timing can still make execution unstable; the tool must report that rather than promise identical outcomes.
- **It does not say a line is correct.** `held` records an individually confirmed unit witness. Group observations are separate and cannot promote member verdicts. Whether an assertion checks the right requirement remains a reviewer's call.
- **The local CLI initiates no network calls or uploads.** This guarantee does not cover subprocess tests or plugins. The later GitHub Action will explicitly publish its documented comment and report artifacts through GitHub.

## How it relates to tools you may already use

Ephorate is built on known techniques and is not the only tool in this area.

- **Mutation testing** (Stryker, PIT, cargo-mutants, mutmut and others) makes small edits to code and reports which edits no test notices. Ephorate's removal trial is a coarse form of the same idea, applied to whole pieces of one change and reported as a reading list instead of a score.
- **Patch minimizers** delete the parts of a change that tests do not need. Ephorate runs the same trial and stops at the report.
- **AI reviewers** interpret the diff and comment. Ephorate will parse changes and run tests without a language model. Its later GitHub comment will summarize trial evidence.

The removal trial itself goes back to delta debugging (Zeller, 1999) and to work on pseudo-tested code (Niedermayr et al., 2016; Vera-Pérez et al., 2019).

## Limits

- The first engine targets native synchronous pytest tests with the supported pytest version and the same Python interpreter as Ephorate. Unittest, doctest, subtests and custom/distributed runners are outside its initial evidence contract.
- Import-origin checks cover modules visible in the pytest process at observer checkpoints, not subprocess/native-extension loading or modules removed between checkpoints.
- It needs a test suite that passes and runs in minutes. Each unit costs at least a partial test run.
- It says nothing useful about configuration, migrations, infrastructure or most UI work.
- An agent can write a shallow test to make a line `held`. Reviewers still read the tests.
- AST equality does not capture every consumer of source text, comments or tool directives. `inert` does not make a change safe to ignore.
- Two stable baseline runs do not prove a suite is free of flakiness. Repeated witnesses and head controls reduce uncertainty; they cannot eliminate it.
- Whether enough of a typical agent change turns out `loose` or `inert` to matter is not known yet. Milestone 2 measures that on real pull requests before anything else is built.

## Status

| Part | State |
|---|---|
| Reconciled documents, site copy and M1 handoff | Complete; browser/publication QA remains separate |
| Engine: units, bounded removal trials, verdicts (Python and pytest) | Implemented; local fixture validation recorded; no public release |
| Replay on real agent pull requests, with a go or no-go decision | Planned |
| Speed: test selection, parallel trials, caching | Planned |
| Agent loop and GitHub Action | Planned |
| Reviewer report, second language, release | Planned |

[PROJECT_PLAN.md](PROJECT_PLAN.md) has the milestones. [AGENTS.md](AGENTS.md) has the standing rules. The [M1 handoff](agent_instruction/what-has-to-be-done/2026-11-15-milestone-1-removal-check.md) remains the implementation contract. CI is configured for macOS/Linux × Python 3.11–3.15; remote CI and Linux execution have not been observed in this session. Work stops before M2 replay.

## Repository layout

```text
README.md            this file
AGENTS.md            standing rules for coding agents
PROJECT_PLAN.md      definitions, design and milestones
index.html           the project site, a single static page
docs/                engineering records (decisions, replay report)
agent_instruction/   handoffs, work records and the development log
src/ephorate/         the local CLI, engine, Git boundary and pytest observer
tests/               synthetic fixtures and regression tests
```

The owner deleted the earlier incident-risk and review-capacity files before supplying this direction. Earlier committed versions remain in Git history; no archive directory exists in the current tree. Do not restore deleted material implicitly.

## The name

The ephorate was Sparta's board of five elected overseers, who could call even the kings to account. It is pronounced EFF-er-it.

## Sources

- Chen and Stratton, ["Artificial Intelligence in the Firm: Bottlenecks in Software Production"](https://fion.ac/jellyfish.pdf), Harvard University, 2026. Figures above are the paper's estimated effects of AI agent adoption, not evidence of Ephorate's usefulness.
- Luo et al., ["Refine After Generation"](https://arxiv.org/html/2608.13292v1), 2026. All 28 evaluated approaches produced larger patches **on average over their resolved SWE-bench Verified tasks**; this is not a claim about every patch or whether each added line was necessary.
- Banik, Chowdhury and Shamim, ["All Smoke, No Alarm"](https://arxiv.org/html/2606.18168v1), 2026. Of 86,156 test-file patch diffs, 80.2% contained weak or no explicit syntactic oracle signals. Modified files may retain existing assertions, and the method does not capture implicit oracles; it does not establish that four out of five complete test files verify nothing.
- Petrović, Ivanković, Fraser and Just, ["Practical Mutation Testing at Scale"](https://arxiv.org/abs/2102.11378), 2021.
- Zeller, "Yesterday, my program worked. Today, it does not. Why?", ESEC/FSE 1999.
- Vera-Pérez, Danglot, Monperrus and Baudry, ["A Comprehensive Study of Pseudo-tested Methods"](https://arxiv.org/abs/1807.05030), Empirical Software Engineering, 2019.
