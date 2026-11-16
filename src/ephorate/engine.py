"""Serial removal trials with conservative reduction and fresh head controls."""

import ast
import platform
import sys
import time
from dataclasses import replace

from ephorate import git, units
from ephorate.models import (
    Baseline,
    CaseResult,
    Change,
    ChangeKind,
    CheckConfig,
    CheckInterrupted,
    CheckReport,
    Environment,
    EphorateError,
    GroupResult,
    IdleResult,
    Reason,
    RunStatus,
    TrialPurpose,
    TrialResult,
    Unit,
    UnitResult,
)
from ephorate.runners.pytest import run_trial


def _outcomes(case: CaseResult) -> tuple[object, ...]:
    return (case.outcome, tuple((p.when, p.outcome, p.was_xfail) for p in case.phases))


def _same_head(first: TrialResult, second: TrialResult) -> bool:
    return (
        first.status == second.status == "passed"
        and first.exit_code == second.exit_code == 0
        and first.collection == second.collection
        and [(c.node_id, _outcomes(c)) for c in first.cases]
        == [(c.node_id, _outcomes(c)) for c in second.cases]
    )


def _cohort(trial: TrialResult, head: TrialResult) -> TrialResult:
    if trial.status in {
        "invalid_evidence",
        "origin_violation",
        "runner_failure",
        "timeout",
        "budget_exhausted",
        "interrupted",
        "patch_failed",
        "structural_failure",
    }:
        return trial
    observed = {case.node_id: case for case in trial.cases}
    mismatch = trial.collection != head.collection or set(observed) != {
        c.node_id for c in head.cases
    }
    for case in head.cases:
        other = observed.get(case.node_id)
        if other is None:
            mismatch = True
        elif case.outcome != "passed":
            mismatch |= _outcomes(case) != _outcomes(other)
        elif other.outcome not in {"passed", "failed"} or any(p.was_xfail for p in other.phases):
            mismatch = True
    return replace(trial, status="cohort_mismatch", reason="cohort_mismatch") if mismatch else trial


def _witnesses(trial: TrialResult) -> tuple[str, ...]:
    return tuple(
        sorted(
            case.node_id
            for case in trial.cases
            if case.outcome == "failed"
            and any(
                p.when == "call"
                and p.outcome == "failed"
                and not p.was_xfail
                and p.exception_category == "assertion"
                for p in case.phases
            )
        )
    )


def _definitions(raw: bytes) -> dict[str, tuple[int, bytes] | None]:
    parsed = ast.parse(raw)
    lines = raw.splitlines(keepends=True)
    result: dict[str, tuple[int, bytes] | None] = {}

    def record(node: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str) -> None:
        key = prefix + node.name
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        text = b"".join(lines[start - 1 : node.end_lineno])
        result[key] = None if key in result else (start, text)

    for node in parsed.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            record(node, "")
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    record(child, node.name + ".")
    return result


def _idle_candidates(change: Change, head: TrialResult, deadline: float) -> list[IdleResult]:
    result: list[IdleResult] = []
    for file in change.files:
        if file.classification != "judge" or not file.path.endswith(".py") or not file.head_blob:
            continue
        ambiguous = False
        try:
            base = _definitions(git.read_blob(change.repo, file.base_blob, deadline))
            current = _definitions(git.read_blob(change.repo, file.head_blob, deadline))
        except (SyntaxError, UnicodeError, ValueError):
            base, current, ambiguous = {}, {}, True
        for case in head.cases:
            if case.path != file.path:
                continue
            name = case.definition_name
            kind: ChangeKind = "unknown"
            reason: Reason = "mapping_ambiguous"
            definition = current.get(name) if name is not None else None
            if (
                not ambiguous
                and name is not None
                and definition is not None
                and case.definition_start == definition[0]
            ):
                if name not in base:
                    kind = "added"
                elif (previous := base[name]) is not None:
                    if previous[1] == definition[1]:
                        continue
                    kind = "modified"
                if kind != "unknown":
                    reason = "run_aborted" if case.outcome == "passed" else "no_passing_baseline"
            result.append(IdleResult(case.node_id, case.path, kind, "unknown", reason, None))
    return sorted(result, key=lambda candidate: candidate.node_id)


class _Check:
    def __init__(self, change: Change, config: CheckConfig, deadline: float) -> None:
        self.change = change
        self.config = config
        self.deadline = deadline
        self.started = deadline - config.budget_seconds
        self.status: RunStatus = "complete"
        self.reason: Reason | None = None
        self.baseline = Baseline()
        self.results: list[UnitResult] = []
        self.trials: list[TrialResult] = []
        self.groups: list[GroupResult] = []
        self.idle: list[IdleResult] = []
        self.environment = Environment(
            platform.python_version(),
            "cpython",
            "macos" if sys.platform == "darwin" else "linux",
            None,
            None,
            None,
        )
        self.head: TrialResult | None = None
        self.trial_timeout = config.min_trial_timeout_seconds

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def execute(
        self, identity: str, purpose: TrialPurpose, selected: tuple[Unit, ...]
    ) -> TrialResult:
        start = time.monotonic()
        ids = tuple(unit.id for unit in selected)
        limit = (
            self.config.baseline_timeout_seconds if purpose == "baseline" else self.trial_timeout
        )
        if not self.remaining():
            trial = TrialResult(
                identity, purpose, ids, "budget_exhausted", "budget_exhausted", None, None, (), 0
            )
        else:
            try:
                with git.snapshot(self.change, self.deadline) as root:
                    if selected:
                        git.apply_units(root, self.change, selected, self.deadline)
                    if not self.remaining():
                        raise EphorateError("budget_exhausted", "trial")
                    trial = run_trial(
                        root,
                        self.change,
                        self.config,
                        identity,
                        purpose,
                        ids,
                        min(limit, self.remaining()),
                    )
            except EphorateError as exc:
                if exc.reason not in {"patch_failed", "budget_exhausted"}:
                    raise
                trial = TrialResult(
                    identity,
                    purpose,
                    ids,
                    exc.reason,
                    exc.reason,
                    None,
                    None,
                    (),
                    time.monotonic() - start,
                )
            except (CheckInterrupted, KeyboardInterrupt):
                self.trials.append(
                    TrialResult(
                        identity,
                        purpose,
                        ids,
                        "interrupted",
                        "interrupted",
                        None,
                        None,
                        (),
                        time.monotonic() - start,
                    )
                )
                raise
        if self.head is not None and purpose != "baseline":
            trial = _cohort(trial, self.head)
        if trial.environment is not None:
            self.environment = replace(trial.environment, git_version=self.environment.git_version)
        self.trials.append(trial)
        return trial

    def prepare(self) -> None:
        self.environment = replace(self.environment, git_version=git.version(self.deadline))
        self.change = units.classify_change(self.change, self.config, self.deadline)
        self.results = [
            UnitResult(u, "unjudged", "run_aborted")
            for u in units.split_change(self.change, self.config, self.deadline)
        ]
        first = self.execute("baseline-1", "baseline", ())
        self.baseline = Baseline((first.id,))
        if first.status != "passed" or first.exit_code != 0:
            raise EphorateError(first.reason or "baseline_failed", "baseline")
        passing = tuple(c.node_id for c in first.cases if c.outcome == "passed")
        if not passing:
            raise EphorateError(
                "no_tests" if not first.cases else "no_passing_baseline", "baseline"
            )
        second = self.execute("baseline-2", "baseline", ())
        self.baseline = Baseline(
            (first.id, second.id),
            passing,
            tuple((c.node_id, c.outcome) for c in first.cases if c.outcome != "passed"),
        )
        if not _same_head(first, second):
            raise EphorateError("baseline_unstable", "baseline")
        self.head = first
        discovered = first.collection.judge_files if first.collection is not None else ()
        self.change = units.classify_change(self.change, self.config, self.deadline, discovered)
        self.results = [
            UnitResult(u, "unjudged", "run_aborted")
            for u in units.split_change(self.change, self.config, self.deadline)
        ]
        self.trial_timeout = max(
            self.config.min_trial_timeout_seconds,
            self.config.timeout_factor * max(first.duration_s, second.duration_s),
        )
        self.idle = _idle_candidates(self.change, first, self.deadline)

    def single_units(self) -> None:
        seen = 0
        files = {file.path: file for file in self.change.files}
        for index, result in enumerate(self.results):
            unit = result.unit
            if unit.classification != "subject":
                self.results[index] = replace(
                    result, reason=files[unit.path].reason or "unsupported_file"
                )
                continue
            seen += 1
            if seen > self.config.max_units:
                self.results[index] = replace(result, reason="unit_cap")
                self.status, self.reason = "partial", "unit_cap"
                continue
            if not units.unit_is_supported(self.change, unit):
                self.results[index] = replace(
                    result, reason=files[unit.path].reason or "unsupported_change"
                )
                continue
            if not self.remaining():
                self.results[index] = replace(result, reason="budget_exhausted")
                self.status, self.reason = "partial", "budget_exhausted"
                continue
            if units.is_inert(self.change, unit, self.deadline):
                self.results[index] = replace(result, verdict="inert", reason="ast_equivalent")
                continue
            first = self.execute(f"unit-{unit.id}-1", "single", (unit,))
            trials = [first.id]
            if first.status == "passed":
                self.results[index] = replace(
                    result,
                    verdict="loose",
                    reason="full_suite_passed_without_unit",
                    trial_ids=tuple(trials),
                )
            elif first.status != "assertion_failure":
                self.results[index] = replace(
                    result, reason=first.reason or "invalid_evidence", trial_ids=tuple(trials)
                )
            else:
                repeat = self.execute(f"unit-{unit.id}-2", "repeat", (unit,))
                trials.append(repeat.id)
                control = self.execute(f"control-{unit.id}", "control", ())
                trials.append(control.id)
                if control.status == "budget_exhausted":
                    self.results[index] = replace(
                        result, reason="budget_exhausted", trial_ids=tuple(trials)
                    )
                elif self.head is None or not _same_head(self.head, control):
                    self.results[index] = replace(
                        result, reason="unstable_control", trial_ids=tuple(trials)
                    )
                    self.results = [
                        replace(r, verdict="unjudged", reason="unstable_control", witnesses=())
                        if r.verdict in {"held", "loose"}
                        else r
                        for r in self.results
                    ]
                    raise EphorateError("unstable_control", "control")
                else:
                    witnesses = tuple(sorted(set(_witnesses(first)) & set(_witnesses(repeat))))
                    confirmed = repeat.status == "assertion_failure" and bool(witnesses)
                    self.results[index] = replace(
                        result,
                        verdict="held" if confirmed else "unjudged",
                        reason="confirmed_assertion" if confirmed else "confirmation_failed",
                        witnesses=witnesses if confirmed else (),
                        trial_ids=tuple(trials),
                    )
            if self.results[index].reason == "budget_exhausted":
                self.status, self.reason = "partial", "budget_exhausted"

    def group_trial(self) -> None:
        members = tuple(r.unit for r in self.results if r.reason == "structural_failure")
        if len(members) < 2:
            return
        trial = self.execute("group-structural-1", "group", members)
        self.groups.append(
            GroupResult(
                "structural-1",
                tuple(u.id for u in members),
                trial.id,
                trial.status,
                _witnesses(trial),
            )
        )
        ids = set(trial.unit_ids)
        self.results = [
            replace(r, group_ids=("structural-1",)) if r.unit.id in ids else r for r in self.results
        ]
        if trial.status == "budget_exhausted":
            self.status, self.reason = "partial", "budget_exhausted"

    def idle_trial(self) -> None:
        if not any(c.reason == "run_aborted" for c in self.idle):
            return
        subjects = tuple(r.unit for r in self.results if r.unit.classification == "subject")
        if len(subjects) > self.config.max_units or any(
            not units.unit_is_supported(self.change, unit) for unit in subjects
        ):
            self.idle = [
                replace(c, reason="unsupported_subject_reversal")
                if c.reason == "run_aborted"
                else c
                for c in self.idle
            ]
            return
        trial = self.execute("idle-all", "idle", subjects)
        observed = {c.node_id: c for c in trial.cases}
        valid = trial.status in {"passed", "assertion_failure"}
        updated: list[IdleResult] = []
        for candidate in self.idle:
            if candidate.reason != "run_aborted":
                updated.append(candidate)
                continue
            case = observed.get(candidate.node_id)
            if not valid or case is None:
                updated.append(
                    replace(candidate, reason=trial.reason or "invalid_evidence", trial_id=trial.id)
                )
            elif case.outcome == "passed":
                updated.append(
                    replace(
                        candidate,
                        status="idle",
                        reason="passed_without_subject_changes",
                        trial_id=trial.id,
                    )
                )
            else:
                updated.append(
                    replace(
                        candidate,
                        status="not_idle",
                        reason="assertion_without_subject_changes",
                        trial_id=trial.id,
                    )
                )
        self.idle = updated
        if trial.status == "budget_exhausted":
            self.status, self.reason = "partial", "budget_exhausted"

    def report(self) -> CheckReport:
        return CheckReport(
            self.change,
            self.config,
            self.status,
            self.reason,
            self.baseline,
            tuple(self.results),
            tuple(self.trials),
            tuple(self.groups),
            tuple(self.idle),
            self.environment,
            max(0, time.monotonic() - self.started),
        )


def check(change: Change, config: CheckConfig, deadline: float) -> CheckReport:
    state = _Check(change, config, deadline)
    try:
        state.prepare()
        state.single_units()
        state.group_trial()
        state.idle_trial()
    except (CheckInterrupted, KeyboardInterrupt):
        state.status, state.reason = "interrupted", "interrupted"
    except EphorateError as exc:
        if exc.reason == "budget_exhausted" and state.head is not None:
            state.status, state.reason = "partial", "budget_exhausted"
            state.results = [
                replace(r, reason="budget_exhausted") if r.reason == "run_aborted" else r
                for r in state.results
            ]
        else:
            state.status, state.reason = "failed", exc.reason
    except (OSError, ValueError):
        state.status, state.reason = "failed", "infrastructure_failure"
    finally:
        try:
            git.verify_source_unchanged(change, time.monotonic() + 30)
        except EphorateError as exc:
            if state.status != "interrupted":
                reason: Reason = (
                    "infrastructure_failure" if exc.reason == "budget_exhausted" else exc.reason
                )
                state.status, state.reason = "failed", reason
    return state.report()
