# Development log

The owner cleared the working files before the removal-check pivot. Earlier chronology is preserved verbatim in [the log at commit 0344822](https://github.com/thedhinakarr/ephorate/blob/03448228bf6838f4cd7d9903e9bc73236e91afc8/agent_instruction/development-log.md). This new working log starts with the reset; it does not imply that earlier history was absent or that deleted references were restored.

## 2026-11-15 — Extract and review the replacement bundle

- The owner supplied `ephorate-pivot.zip` and requested extraction, complete reading and a plan. The archive contained five text files totaling 66,262 bytes. Verified CRC, paths, file types and extracted-byte equality; left Git metadata and `.gitignore` unchanged.
- Read all five files, including website CSS/JavaScript and the embedded future handoff. Did not treat its quoted implementation prompt as an assignment.
- Identified stale reset/archive assumptions, contradictory verdict and baseline rules, unreliable JUnit exception classification, collective-attribution risks, limited AST evidence, unsafe copy guarantees and delayed M1 safeguards.
- Checked primary research/API documentation and wrote the review-and-plan note. HTML structure/IDs/fragments and declared 22/11 counts passed source checks. No browser behavior, engine tests, installation, commit, push or publication was performed.

## 2026-11-15 — Accept corrections and prepare Milestone 1

- The owner authorized updating the plan with the corrections and preparing a decision-complete OpenCode M1 handoff, explicitly saying not to implement the engine. The owner selected **MIT**; added the license and recorded that it does not relicense third-party material.
- Reconciled the root plan/rules and product copy; replaced the stale reset procedure; created the current index, log and decisions. Preserved intentional deletions and the original replacement ZIP. Earlier incident-risk and review-capacity content remains in Git history.
- Defined M1's committed-snapshot scope, independent scratch clones, typed pytest evidence, stable-baseline/cohort rules, assertion confirmation, group-only observations, limited AST/idle evidence, source-origin checks, budgets, output contract and fixture/CI acceptance. The handoff is a future assignment; no engine files or milestone completion records were created.
- Website layout, JavaScript and accessibility implementation are not part of this documentation correction. Browser/publication QA remains pending. Package/runtime compatibility must be demonstrated during M1, not inferred from release metadata.
- Documentation validation passed: active local Markdown links, all eight required handoff sections, HTML tag balance/unique IDs/internal fragments, and the illustrative 22-total/11-reading-list counts. CSS and JavaScript match the supplied ZIP byte-for-byte; its SHA-256 remains `73fcd9ecab8eb1e997b4d0b0a45639f715d051e0b68dab7ef3047dcdfade3aa6`. `git diff --check` passed. Confirmed that no `src/`, `tests/`, package manifest, lockfile or CI workflow was created. These are source/document checks, not engine or browser validation.
- No commits, pushes, pull requests, engine execution, external repository replay or deployment are included in this assignment. Next: explicitly assign the M1 handoff; after it passes, report actual results and stop before M2.

## 2026-11-15 — Milestone 1 implementation assigned

- The owner explicitly requested "implement the milestone 1", superseding the preceding planning-only assignment. Implementation is in progress on `implementation/removal-check-m1`, preserving the existing documentation changes and intentional deletions.
- This authorizes the handoff's engine, generated fixtures, package/lockfile, formatter, lint/type/test/build checks and CI configuration. It does not assign M2 replay, pushing, merging or publishing. Completion and observed validation will be recorded after the checks run.

## 2026-11-15 — Milestone 1 implemented and validated locally

- Built the standard-library CLI, Git/scratch boundary, pytest observer, conservative verdict engine, report schema/output, synthetic fixtures, pinned package and CI configuration. Updated active documentation and site status copy; preserved CSS/JavaScript, original ZIP, intentional deletions and Git history.
- Review added regressions for final Git-filter checks, wrapped callable identity, complete cohorts, namespace/`src/` imports, ignored virtual environments, unsafe temporary-directory selection and blocked output. Final development suite: **205 passed** on CPython 3.15.2; lint, formatting, strict typing, sdist/wheel and installed-wheel smoke checks passed. Earlier complete suites and later targeted regressions also passed on macOS Python 3.11–3.14.
- [Implementation record](what-was-done/2026-11-15-milestone-1.md) and [validation record](what-was-the-result/2026-11-15-milestone-1.md) contain actual scope, commands and platform limits. An independent fresh local checkout/environment also passed all **205 tests** and the sdist/wheel build; its temporary source commit never touched the original Git history.
- No original-repository commit, push, merge, external replay, publishing or deploy. Remote CI/Linux execution and browser/publication QA remain unobserved. Stop before M2; its repository selection and continuation still need the owner.

## 2026-11-16 — Milestone 1 commit and push authorized

- The owner explicitly requested committing and pushing M1 to the personal Ephorate repository. Verified `thedhinakarr/ephorate` is public, owned by the authenticated personal user, and matches the local origin URL.
- Prepared `implementation/removal-check-m1` with the reviewed engine, fixtures, package/lockfile, CI, schema, license, planning and validation records, plus the earlier intentional reset deletions. Environment, build and cache artifacts are excluded. Existing 205-test and fresh-checkout validation remains recorded above; no engine changes were made during publication preparation.
- This assignment authorizes the branch commit and push. It does not assign a merge into main, M2 replay, PyPI publishing or deployment.
