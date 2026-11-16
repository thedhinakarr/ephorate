# GitHub publication results — 2026-11-16

## Deployment

- Personal public repository: `thedhinakarr/ephorate`; M1 branch: `implementation/removal-check-m1`.
- Initial site source: `c1c50b07c4337e1c39093e52901cced0f30eb727`. Initial content-only Pages commit: `f016e39452123a9cc9fee340caf573d28ad71088`.
- [Pages build](https://github.com/thedhinakarr/ephorate/actions/runs/43863999604) completed. API reported `built`, no error, source `gh-pages:/`, HTTPS enforced and no custom domain.
- [Live site](https://thedhinakarr.github.io/ephorate/) returned HTTP 200 and matched the source byte-for-byte: 34,000 bytes, SHA-256 `d8bdcd0d3380fdc3db819deb7b55e47c88baf1ca92d18b4695457668572e52bc`. A browser visit displayed the current Ephorate copy and settled at 22 changed lines / 11 left to read, with no recorded warning/error console messages.
- Final wording refresh removed the now-stale "remote CI unobserved" claim. Pages commit `26cb71e0a61060c299e517de0dcacb90e9791599` reported `built` with no error. The live HTTP 200 response matched the final local HTML: 34,009 bytes, SHA-256 `acf5e57d2d72b12dad206421222149fe8d743e65ccdffe3c509c606995ab9f4f`.

## Site checks

- Desktop at 1440 px and narrow layout at 390 px: content remained within the viewport. At 390 px, the 620 px table remained inside its named 350 px scroll region; keyboard ArrowRight moved it by 40 px.
- Enter opened held example code; Enter on Run again reset the reading count to 22 and it settled back to 11. Held/inert disclosures closed while loose/unjudged code stayed open.
- Focus inspection showed a 3 px blue outline on the light scroll region and a 3 px light outline in the dark footer. Native summaries and overflow regions are keyboard-focusable.
- Script-disabled browser frame: the unmodified site rendered all six code units, the disabled Run button, 22/22 static counters and its explicit no-script explanation of the illustrative 22/11 result. No browser-wide JavaScript preference was changed.
- Reduced-motion paths: a temporary copy forced the existing JavaScript branch and CSS media block. Browser results were 22/11, enabled rerun, `scroll-behavior: auto` and zero transition duration, without warning/error console messages. A separate Node self-check exercised normal/reduced scheduling and reset behavior. Native operating-system preference detection was not toggled; this is branch testing, not an OS accessibility certification.
- All six distinct external anchor destinations returned HTTP 200, including current-branch source/plan links and the three research sources. HTML balance, unique IDs, fragment/label targets and `git diff --check` passed.

## Remote engine CI

- [Initial M1 run](https://github.com/thedhinakarr/ephorate/actions/runs/43863728542), commit `4a3c04c8`: all ten macOS/Linux × Python 3.11–3.15 jobs passed.
- [Site follow-up run](https://github.com/thedhinakarr/ephorate/actions/runs/43863940690), commit `c1c50b0`: nine jobs passed. macOS/Python 3.13 reported 204 passed and one failure in `test_remaining_unsupported_git_states_preserve_fixture[submodule]`. An empty `.git/objects/maintenance.lock` disappeared between the strict source snapshots; the other 37 files matched. The fixture helper allowed detached automatic Git maintenance, while the production Git boundary already disabled it. This identifies a fixture-maintenance race; do not weaken the preservation assertion or silently disregard the failed run.
- After disabling fixture automatic maintenance/garbage collection, the locked local suite passed **205 tests in 110.32 s** on macOS CPython 3.15.2. The targeted Git/unit suite passed **33 tests in 8.95 s**; Ruff, format checking (22 unchanged files) and `git diff --check` passed. The strict preservation assertion remains unchanged. Remote verification of this follow-up is recorded in the branch's subsequent CI run.

Package publication and real-PR usefulness remain unvalidated. The local engine's earlier 205-test results are preserved in the dated M1 record.
