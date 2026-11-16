"""Immutable records shared by the Git, runner, engine and report boundaries."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FileClass = Literal["judge", "subject", "other"]
UnitKind = Literal["hunk", "add_file", "delete_file", "file"]
Verdict = Literal["held", "loose", "inert", "unjudged"]
Outcome = Literal["passed", "failed", "skipped", "xfailed", "xpassed", "unknown"]
Phase = Literal["setup", "call", "teardown"]
PhaseOutcome = Literal["passed", "failed", "skipped"]
ExceptionCategory = Literal["none", "assertion", "structural", "runtime", "unknown"]
TrialPurpose = Literal["baseline", "single", "repeat", "control", "group", "idle"]
TrialStatus = Literal[
    "passed",
    "assertion_failure",
    "structural_failure",
    "runtime_failure",
    "phase_failure",
    "cohort_mismatch",
    "origin_violation",
    "invalid_evidence",
    "runner_failure",
    "timeout",
    "budget_exhausted",
    "interrupted",
    "patch_failed",
]
RunStatus = Literal["complete", "partial", "failed", "interrupted"]
IdleStatus = Literal["idle", "not_idle", "unknown"]
ChangeKind = Literal["added", "modified", "unknown"]
Reason = Literal[
    "confirmed_assertion",
    "full_suite_passed_without_unit",
    "ast_equivalent",
    "judge_protected",
    "unsupported_file",
    "excluded_pattern",
    "source_root_mismatch",
    "unsupported_change",
    "unsupported_module",
    "ambiguous_judge",
    "patch_failed",
    "structural_failure",
    "runtime_failure",
    "phase_failure",
    "cohort_mismatch",
    "origin_violation",
    "invalid_evidence",
    "evidence_limit",
    "unsupported_collection",
    "unsupported_runner",
    "runner_failure",
    "timeout",
    "budget_exhausted",
    "unit_cap",
    "confirmation_failed",
    "unstable_control",
    "baseline_failed",
    "baseline_unstable",
    "no_tests",
    "configuration_error",
    "unsafe_repository",
    "missing_ref",
    "missing_object",
    "source_changed",
    "infrastructure_failure",
    "output_error",
    "interrupted",
    "run_aborted",
    "mapping_ambiguous",
    "no_passing_baseline",
    "unsupported_subject_reversal",
    "passed_without_subject_changes",
    "assertion_without_subject_changes",
]


class EphorateError(Exception):
    def __init__(self, reason: Reason, operation: str) -> None:
        self.reason = reason
        self.operation = operation
        super().__init__(f"{operation}: {reason}")


class CheckInterrupted(BaseException):
    def __init__(self, signum: int) -> None:
        self.signum = signum
        super().__init__(signum)


@dataclass(frozen=True)
class CheckConfig:
    repo: Path
    base_ref: str | None = None
    source_root: str = "."
    pytest_argv: tuple[str, ...] = ("-q",)
    judge_patterns: tuple[str, ...] = ()
    other_patterns: tuple[str, ...] = ()
    max_units: int = 50
    budget_seconds: float = 900
    baseline_timeout_seconds: float = 300
    min_trial_timeout_seconds: float = 30
    timeout_factor: float = 3
    fail_on: tuple[str, ...] = ()
    output: Path | None = None


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str
    base_blob: str | None
    head_blob: str | None
    base_mode: str | None
    head_mode: str | None
    classification: FileClass
    reason: Reason | None
    additions: int | None
    deletions: int | None


@dataclass(frozen=True)
class SourceState:
    head_sha: str
    index_sha256: str
    refs: tuple[tuple[str, str], ...]
    tracked_files: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Change:
    repo: Path
    git_dir: Path
    common_dir: Path
    base_sha: str
    head_sha: str
    base_tree: str
    head_tree: str
    files: tuple[FileChange, ...]
    source_state: SourceState


@dataclass(frozen=True)
class Unit:
    id: str
    path: str
    kind: UnitKind
    ordinal: int
    base_start: int
    base_count: int
    head_start: int
    head_count: int
    additions: int | None
    deletions: int | None
    patch: bytes
    classification: FileClass


@dataclass(frozen=True)
class PhaseResult:
    when: Phase
    outcome: PhaseOutcome
    was_xfail: bool
    exception_category: ExceptionCategory
    exception_types: tuple[str, ...]


@dataclass(frozen=True)
class CaseResult:
    node_id: str
    path: str
    definition_name: str | None
    definition_start: int | None
    definition_end: int | None
    outcome: Outcome
    phases: tuple[PhaseResult, ...]


@dataclass(frozen=True)
class Collection:
    selected: tuple[str, ...]
    deselected: tuple[str, ...]
    judge_files: tuple[str, ...]
    skipped_paths: tuple[str, ...]
    error: bool


@dataclass(frozen=True)
class Environment:
    python_version: str
    implementation: str
    platform: str
    git_version: str | None
    pytest_version: str | None
    plugins: tuple[tuple[str, str | None], ...] | None


@dataclass(frozen=True)
class TrialResult:
    id: str
    purpose: TrialPurpose
    unit_ids: tuple[str, ...]
    status: TrialStatus
    reason: Reason | None
    exit_code: int | None
    collection: Collection | None
    cases: tuple[CaseResult, ...]
    duration_s: float
    environment: Environment | None = None


@dataclass(frozen=True)
class UnitResult:
    unit: Unit
    verdict: Verdict
    reason: Reason
    witnesses: tuple[str, ...] = ()
    trial_ids: tuple[str, ...] = ()
    group_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroupResult:
    id: str
    unit_ids: tuple[str, ...]
    trial_id: str
    status: TrialStatus
    assertion_nodes: tuple[str, ...]


@dataclass(frozen=True)
class IdleResult:
    node_id: str
    path: str
    change: ChangeKind
    status: IdleStatus
    reason: Reason
    trial_id: str | None


@dataclass(frozen=True)
class Baseline:
    trial_ids: tuple[str, ...] = ()
    passing: tuple[str, ...] = ()
    excluded: tuple[tuple[str, Outcome], ...] = ()


@dataclass(frozen=True)
class CheckReport:
    change: Change
    config: CheckConfig
    status: RunStatus
    reason: Reason | None
    baseline: Baseline
    units: tuple[UnitResult, ...]
    trials: tuple[TrialResult, ...]
    groups: tuple[GroupResult, ...]
    idle_tests: tuple[IdleResult, ...]
    environment: Environment
    total_duration_s: float
