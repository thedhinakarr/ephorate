"""The sole subprocess boundary for pytest, with fail-closed evidence decoding."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, cast

from ephorate import git, units
from ephorate.models import (
    CaseResult,
    Change,
    CheckConfig,
    Collection,
    Environment,
    EphorateError,
    ExceptionCategory,
    Outcome,
    Phase,
    PhaseOutcome,
    PhaseResult,
    Reason,
    TrialPurpose,
    TrialResult,
    TrialStatus,
)

MAX_BYTES = 16 * 1024 * 1024
MAX_CASES = 100_000
MAX_STRING = 16 * 1024


class InvalidEvidence(Exception):
    def __init__(self, reason: Reason = "invalid_evidence") -> None:
        self.reason = reason
        super().__init__(reason)


def _keys(value: object, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise InvalidEvidence()
    return cast(dict[str, Any], value)


def _string(value: object) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise InvalidEvidence()
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as error:
        raise InvalidEvidence() from error
    if size > MAX_STRING:
        raise InvalidEvidence("evidence_limit")
    return value


def _strings(value: object, *, ordered: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise InvalidEvidence()
    result = tuple(_string(item) for item in value)
    if len(set(result)) != len(result) or (not ordered and result != tuple(sorted(result))):
        raise InvalidEvidence()
    return result


def _path(value: object) -> str:
    text = _string(value)
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or text != path.as_posix():
        raise InvalidEvidence()
    return text


def _node(value: object) -> str:
    text = _string(value)
    _path(text.split("::", 1)[0])
    return text


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise InvalidEvidence()
    return value


def _integer(value: object, *, positive: bool = False) -> int:
    if type(value) is not int or (positive and value < 1):
        raise InvalidEvidence()
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidEvidence()
        result[key] = value
    return result


def _bad_constant(value: str) -> object:
    raise InvalidEvidence()


def _terminal(phases: tuple[PhaseResult, ...]) -> Outcome:
    if any(phase.outcome == "failed" for phase in phases):
        return "failed"
    skipped = next((phase for phase in phases if phase.outcome == "skipped"), None)
    if skipped is not None:
        return "xfailed" if skipped.was_xfail else "skipped"
    call = next(phase for phase in phases if phase.when == "call")
    return "xpassed" if call.was_xfail else "passed"


def _reduce(
    collection: Collection, cases: tuple[CaseResult, ...], exit_code: int
) -> tuple[TrialStatus, Reason | None]:
    if collection.error:
        if exit_code not in (1, 2):
            raise InvalidEvidence()
        return "structural_failure", "structural_failure"
    if not collection.selected:
        if exit_code not in (0, 5):
            raise InvalidEvidence()
        return "runner_failure", "no_tests"
    failed = [phase for case in cases for phase in case.phases if phase.outcome == "failed"]
    if (exit_code == 0 and failed) or (exit_code == 1 and not failed) or exit_code not in (0, 1):
        raise InvalidEvidence()
    if any(phase.exception_category == "structural" for phase in failed):
        return "structural_failure", "structural_failure"
    if any(phase.when != "call" for phase in failed):
        return "phase_failure", "phase_failure"
    if any(phase.exception_category != "assertion" or phase.was_xfail for phase in failed):
        return "runtime_failure", "runtime_failure"
    if failed:
        return "assertion_failure", None
    return "passed", None


def _decode_evidence(
    payload: bytes, exit_code: int
) -> tuple[Collection, tuple[CaseResult, ...], TrialStatus, Reason | None, Environment]:
    if len(payload) > MAX_BYTES:
        raise InvalidEvidence("evidence_limit")
    if not payload.endswith(b"\n"):
        raise InvalidEvidence()
    try:
        events = [
            json.loads(line, object_pairs_hook=_unique_object, parse_constant=_bad_constant)
            for line in payload.decode("utf-8").splitlines()
        ]
    except (ValueError, UnicodeError, RecursionError) as error:
        raise InvalidEvidence() from error
    if len(events) < 3:
        raise InvalidEvidence()
    start = _keys(
        events[0],
        {"event", "protocol", "python_version", "pytest_version", "supported_options", "plugins"},
    )
    finish = _keys(events[-1], {"event", "exit_code", "origin_valid", "error_reason"})
    if start["event"] != "start" or _integer(start["protocol"]) != 1 or finish["event"] != "finish":
        raise InvalidEvidence()
    if _integer(finish["exit_code"]) != exit_code:
        raise InvalidEvidence()
    if finish["error_reason"] == "evidence_limit":
        raise InvalidEvidence("evidence_limit")
    python_version = _string(start["python_version"])
    pytest_version = None if start["pytest_version"] is None else _string(start["pytest_version"])
    supported = _boolean(start["supported_options"])
    origin_valid = _boolean(finish["origin_valid"])
    plugins: list[tuple[str, str | None]] = []
    if not isinstance(start["plugins"], list):
        raise InvalidEvidence()
    for plugin in start["plugins"]:
        if not isinstance(plugin, list) or len(plugin) != 2:
            raise InvalidEvidence()
        name = _string(plugin[0])
        if name.startswith("/") or "\x00" in name:
            raise InvalidEvidence()
        version = None if plugin[1] is None else _string(plugin[1])
        plugins.append((name, version))
    if len({name for name, _ in plugins}) != len(plugins) or plugins != sorted(plugins):
        raise InvalidEvidence()
    environment = Environment(
        python_version,
        "cpython",
        "macos" if sys.platform == "darwin" else "linux",
        None,
        pytest_version,
        tuple(plugins),
    )
    items: dict[str, tuple[str, str | None, int | None, int | None]] = {}
    collection: Collection | None = None
    phases: dict[str, list[PhaseResult]] = {}
    for raw in events[1:-1]:
        if not isinstance(raw, dict):
            raise InvalidEvidence()
        if raw.get("event") == "item":
            item = _keys(
                raw,
                {
                    "event",
                    "node_id",
                    "path",
                    "definition_name",
                    "definition_start",
                    "definition_end",
                },
            )
            if collection is not None:
                raise InvalidEvidence()
            node = _node(item["node_id"])
            if node in items:
                raise InvalidEvidence()
            if len(items) >= MAX_CASES:
                raise InvalidEvidence("evidence_limit")
            path = _path(item["path"])
            definition = (
                None if item["definition_name"] is None else _string(item["definition_name"])
            )
            first = (
                None
                if item["definition_start"] is None
                else _integer(item["definition_start"], positive=True)
            )
            last = (
                None
                if item["definition_end"] is None
                else _integer(item["definition_end"], positive=True)
            )
            if (definition is None) != (first is None) or (first is None) != (last is None):
                raise InvalidEvidence()
            if first is not None and last is not None and first > last:
                raise InvalidEvidence()
            items[node] = (path, definition, first, last)
        elif raw.get("event") == "collection":
            event = _keys(
                raw,
                {
                    "event",
                    "selected",
                    "deselected",
                    "judge_files",
                    "skipped_paths",
                    "collection_error",
                },
            )
            if collection is not None:
                raise InvalidEvidence()
            selected = _strings(event["selected"], ordered=True)
            deselected = _strings(event["deselected"])
            for node in (*selected, *deselected):
                _node(node)
            judges = _strings(event["judge_files"])
            skipped = _strings(event["skipped_paths"])
            for path in (*judges, *skipped):
                _path(path)
            collection = Collection(
                selected, deselected, judges, skipped, _boolean(event["collection_error"])
            )
            if set(selected) & set(deselected) or set(items) != set(selected) | set(deselected):
                raise InvalidEvidence()
            if not set(skipped) <= set(judges) or any(
                item[0] not in judges for item in items.values()
            ):
                raise InvalidEvidence()
            phases = {node: [] for node in selected}
        elif raw.get("event") == "phase":
            event = _keys(
                raw,
                {
                    "event",
                    "node_id",
                    "when",
                    "outcome",
                    "was_xfail",
                    "exception_category",
                    "exception_types",
                },
            )
            node = _node(event["node_id"])
            if collection is None or node not in phases:
                raise InvalidEvidence()
            when, outcome, category = event["when"], event["outcome"], event["exception_category"]
            if when not in ("setup", "call", "teardown") or outcome not in (
                "passed",
                "failed",
                "skipped",
            ):
                raise InvalidEvidence()
            if category not in ("none", "assertion", "structural", "runtime", "unknown"):
                raise InvalidEvidence()
            prior = phases[node]
            expected = (
                "setup"
                if not prior
                else "call"
                if len(prior) == 1 and prior[0].outcome == "passed"
                else "teardown"
            )
            if when != expected or len(prior) >= 3 or (prior and prior[-1].when == "teardown"):
                raise InvalidEvidence()
            exception_types = _strings(event["exception_types"])
            if category == "none" and exception_types:
                raise InvalidEvidence()
            prior.append(
                PhaseResult(
                    cast(Phase, when),
                    cast(PhaseOutcome, outcome),
                    _boolean(event["was_xfail"]),
                    cast(ExceptionCategory, category),
                    exception_types,
                )
            )
        else:
            raise InvalidEvidence()
    if collection is None:
        raise InvalidEvidence()
    reason = finish["error_reason"]
    if reason not in (
        None,
        "unsupported_runner",
        "unsupported_collection",
        "origin_violation",
        "evidence_limit",
        "invalid_evidence",
    ):
        raise InvalidEvidence()
    if not origin_valid or reason == "origin_violation":
        return collection, (), "origin_violation", "origin_violation", environment
    if reason is not None:
        status: TrialStatus = (
            "invalid_evidence"
            if reason in ("evidence_limit", "invalid_evidence")
            else "runner_failure"
        )
        return collection, (), status, cast(Reason, reason), environment
    if not supported or pytest_version != "9.2.0":
        return collection, (), "runner_failure", "unsupported_runner", environment
    cases: list[CaseResult] = []
    abort_before_execution = collection.error and not any(phases.values())
    for node in collection.selected:
        recorded = tuple(phases[node])
        if abort_before_execution:
            continue
        if not recorded or recorded[-1].when != "teardown":
            raise InvalidEvidence()
        cases.append(CaseResult(node, *items[node], _terminal(recorded), recorded))
    status, result_reason = _reduce(collection, tuple(cases), exit_code)
    return collection, tuple(cases), status, result_reason, environment


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    end = time.monotonic() + 2
    try:
        while time.monotonic() < end:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            except PermissionError:
                # macOS can report EPERM for a group whose leader just became a zombie.
                # Reap it before retrying; a real permission failure still fails the final kill.
                process.poll()
            time.sleep(0.02)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_trial(
    root: Path,
    change: Change,
    config: CheckConfig,
    trial_id: str,
    purpose: TrialPurpose,
    unit_ids: tuple[str, ...],
    timeout_s: float,
) -> TrialResult:
    started = time.monotonic()
    deadline = started + timeout_s
    if timeout_s <= 0:
        return TrialResult(
            trial_id, purpose, unit_ids, "budget_exhausted", "budget_exhausted", None, None, (), 0
        )
    try:
        modules = units.project_modules(change, config, deadline)
        trees = [
            git.read_tree(change.repo, revision, deadline)
            for revision in (change.base_sha, change.head_sha)
        ]
    except EphorateError as error:
        if error.reason != "budget_exhausted":
            raise
        return TrialResult(
            trial_id,
            purpose,
            unit_ids,
            "timeout",
            "timeout",
            None,
            None,
            (),
            time.monotonic() - started,
        )
    tracked = sorted({path for tree in trees for path in tree if path.endswith(".py")})
    if "_ephorate_observer" in modules:
        return TrialResult(
            trial_id,
            purpose,
            unit_ids,
            "runner_failure",
            "unsupported_runner",
            None,
            None,
            (),
            time.monotonic() - started,
        )
    for name, path in list(modules.items()):
        parts = name.split(".")
        relative = PurePosixPath(path)
        is_package = relative.name == "__init__.py"
        for length in range(1, len(parts)):
            parent = ".".join(parts[:length])
            if parent not in modules:
                ascend = len(parts) - length + int(is_package)
                modules[parent] = relative.parents[ascend - 1].as_posix()
    excluded = tuple(
        path.resolve() for path in (change.repo, change.git_dir, change.common_dir, root)
    )
    for candidate in (Path("/tmp"), Path("/var/tmp")):
        temporary_parent = candidate.resolve()
        if temporary_parent.is_dir() and not any(
            temporary_parent.is_relative_to(path) for path in excluded
        ):
            break
    else:
        raise EphorateError("infrastructure_failure", "runner temporary parent")
    try:
        with tempfile.TemporaryDirectory(
            prefix="ephorate-runner-", dir=temporary_parent
        ) as temporary:
            private = Path(temporary)
            if any(
                private.resolve().is_relative_to(path.resolve())
                for path in (change.repo, change.git_dir, change.common_dir, root)
            ):
                raise EphorateError("infrastructure_failure", "runner temporary directory")
            manifest = private / "manifest.json"
            evidence = private / "evidence.jsonl"
            for private_path in (manifest, evidence):
                private_path.touch(mode=0o600, exist_ok=False)
            manifest.write_text(
                json.dumps(
                    {
                        "root": str(root.resolve()),
                        "original": str(change.repo.resolve()),
                        "source_root": config.source_root,
                        "modules": modules,
                        "tracked": tracked,
                        "argv": config.pytest_argv,
                        "evidence": str(evidence),
                        "observer": str(Path(__file__).with_name("observer.py").resolve()),
                    }
                ),
                encoding="utf-8",
            )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return TrialResult(
                    trial_id,
                    purpose,
                    unit_ids,
                    "timeout",
                    "timeout",
                    None,
                    None,
                    (),
                    time.monotonic() - started,
                )
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(Path(__file__).with_name("bootstrap.py").resolve()),
                    str(manifest),
                ],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            timed_out = False
            try:
                try:
                    exit_code = process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    exit_code = None
            finally:
                _terminate_group(process)
            if timed_out:
                return TrialResult(
                    trial_id,
                    purpose,
                    unit_ids,
                    "timeout",
                    "timeout",
                    exit_code,
                    None,
                    (),
                    time.monotonic() - started,
                )
            with evidence.open("rb") as stream:
                payload = stream.read(MAX_BYTES + 1)
            try:
                assert exit_code is not None
                collection, cases, status, reason, environment = _decode_evidence(
                    payload, exit_code
                )
            except InvalidEvidence as error:
                return TrialResult(
                    trial_id,
                    purpose,
                    unit_ids,
                    "invalid_evidence",
                    error.reason,
                    exit_code,
                    None,
                    (),
                    time.monotonic() - started,
                )
            return TrialResult(
                trial_id,
                purpose,
                unit_ids,
                status,
                reason,
                exit_code,
                collection,
                cases,
                time.monotonic() - started,
                environment,
            )
    except OSError as error:
        raise EphorateError("infrastructure_failure", "pytest process or evidence I/O") from error
