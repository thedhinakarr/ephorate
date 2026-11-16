"""Runner boundary checks: real child execution plus malformed typed evidence."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from ephorate import git, units
from ephorate.models import (
    Change,
    CheckConfig,
    CheckInterrupted,
    EphorateError,
    SourceState,
    TrialResult,
)
from ephorate.runners import observer
from ephorate.runners import pytest as runner


def packet(
    *, outcome: str = "passed", category: str = "none", exit_code: int = 0
) -> list[dict[str, Any]]:
    node = "test_module.py::test_value"
    return [
        {
            "event": "start",
            "protocol": 1,
            "python_version": "3.15.2",
            "pytest_version": "9.2.0",
            "supported_options": True,
            "plugins": [],
        },
        {
            "event": "item",
            "node_id": node,
            "path": "test_module.py",
            "definition_name": "test_value",
            "definition_start": 1,
            "definition_end": 2,
        },
        {
            "event": "collection",
            "selected": [node],
            "deselected": [],
            "judge_files": ["test_module.py"],
            "skipped_paths": [],
            "collection_error": False,
        },
        {
            "event": "phase",
            "node_id": node,
            "when": "setup",
            "outcome": "passed",
            "was_xfail": False,
            "exception_category": "none",
            "exception_types": [],
        },
        {
            "event": "phase",
            "node_id": node,
            "when": "call",
            "outcome": outcome,
            "was_xfail": False,
            "exception_category": category,
            "exception_types": [] if category == "none" else ["builtins.AssertionError"],
        },
        {
            "event": "phase",
            "node_id": node,
            "when": "teardown",
            "outcome": "passed",
            "was_xfail": False,
            "exception_category": "none",
            "exception_types": [],
        },
        {"event": "finish", "exit_code": exit_code, "origin_valid": True, "error_reason": None},
    ]


def encoded(events: list[dict[str, Any]]) -> bytes:
    return ("\n".join(json.dumps(event) for event in events) + "\n").encode()


@pytest.mark.parametrize(
    ("outcome", "category", "code", "status"),
    [
        ("passed", "none", 0, "passed"),
        ("failed", "assertion", 1, "assertion_failure"),
        ("failed", "structural", 1, "structural_failure"),
        ("failed", "runtime", 1, "runtime_failure"),
    ],
)
def test_typed_reduction(outcome: str, category: str, code: int, status: str) -> None:
    result = runner._decode_evidence(
        encoded(packet(outcome=outcome, category=category, exit_code=code)), code
    )
    assert result[2] == status
    assert result[0].selected == ("test_module.py::test_value",)
    assert result[4].pytest_version == "9.2.0"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_finish",
        "missing_teardown",
        "duplicate_phase",
        "unknown_key",
        "wrong_exit",
        "duplicate_node",
        "absolute",
        "bad_order",
        "unknown_event",
        "missing_item",
    ],
)
def test_malformed_evidence_fails_closed(mutation: str) -> None:
    events = packet()
    if mutation == "missing_finish":
        events.pop()
    elif mutation == "missing_teardown":
        events.pop(-2)
    elif mutation == "duplicate_phase":
        events.insert(-1, events[-2].copy())
    elif mutation == "unknown_key":
        events[0]["captured_output"] = "must never be accepted"
    elif mutation == "wrong_exit":
        events[-1]["exit_code"] = 1
    elif mutation == "duplicate_node":
        events[2]["selected"] *= 2
    elif mutation == "absolute":
        events[1]["path"] = "/private/project/test_module.py"
    elif mutation == "bad_order":
        events[3], events[4] = events[4], events[3]
    elif mutation == "unknown_event":
        events[4]["event"] = "captured"
    elif mutation == "missing_item":
        events.pop(1)
    with pytest.raises(runner.InvalidEvidence):
        runner._decode_evidence(encoded(events), 0)


def test_duplicate_json_keys_and_size_limits() -> None:
    with pytest.raises(runner.InvalidEvidence):
        runner._decode_evidence(b'{"event":"start","event":"finish"}\n', 0)
    with pytest.raises(runner.InvalidEvidence, match="evidence_limit"):
        runner._decode_evidence(b" " * (runner.MAX_BYTES + 1), 0)
    events = packet()
    events[1]["definition_name"] = "x" * (runner.MAX_STRING + 1)
    with pytest.raises(runner.InvalidEvidence, match="evidence_limit"):
        runner._decode_evidence(encoded(events), 0)


def test_collection_error_can_abort_before_all_phases() -> None:
    events = packet()
    events[2]["collection_error"] = True
    events[-1]["exit_code"] = 2
    events = events[:3] + events[-1:]
    result = runner._decode_evidence(encoded(events), 2)
    assert result[2] == "structural_failure"
    assert result[1] == ()


def test_stable_xfail_is_not_a_witness() -> None:
    events = packet(outcome="skipped", category="assertion")
    events[4]["was_xfail"] = True
    result = runner._decode_evidence(encoded(events), 0)
    assert result[2] == "passed"
    assert result[1][0].outcome == "xfailed"


@pytest.mark.parametrize("suppress", [False, True])
def test_exception_graph_keeps_suppressed_structural_context(suppress: bool) -> None:
    try:
        try:
            raise ImportError("private detail")
        except ImportError:
            if suppress:
                raise AssertionError("private assertion") from None
            raise AssertionError("private assertion") from ImportError("another private detail")
    except AssertionError as error:
        category, names = observer.exception_evidence(error)
    assert category == "structural"
    assert "builtins.ImportError" in names
    assert all("private" not in name for name in names)


def test_exception_group_and_graph_limit_never_witness() -> None:
    category, _ = observer.exception_evidence(ExceptionGroup("secret", [AssertionError()]))
    assert category == "runtime"
    error = AssertionError()
    for _ in range(20):
        parent = AssertionError()
        parent.__cause__ = error
        error = parent
    assert observer.exception_evidence(error)[0] == "unknown"


def run_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    *,
    module: str = "def value():\n    return 2\n",
    options: tuple[str, ...] = ("-q",),
    extra: dict[str, str] | None = None,
    timeout: float = 15,
) -> tuple[TrialResult, Path]:
    original = tmp_path / "original"
    root = tmp_path / "scratch"
    original.mkdir()
    root.mkdir()
    files = {"module.py": module, "test_module.py": source, **(extra or {})}
    for name, content in files.items():
        for directory in (original, root):
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    monkeypatch.setattr(units, "project_modules", lambda *_: {"module": "module.py"})
    monkeypatch.setattr(git, "read_tree", lambda *_: {name: None for name in files})
    change = Change(
        original,
        original / ".git",
        original / ".git",
        "a" * 40,
        "b" * 40,
        "c" * 40,
        "d" * 40,
        (),
        SourceState("b" * 40, "e" * 64, (), ()),
    )
    config = CheckConfig(original, pytest_argv=options)
    result = runner.run_trial(root, change, config, "single", "single", (), timeout)
    return result, root


@pytest.mark.parametrize(("assertion", "status"), [("2", "passed"), ("3", "assertion_failure")])
def test_real_native_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, assertion: str, status: str
) -> None:
    result, root = run_source(
        tmp_path,
        monkeypatch,
        f"from module import value\ndef test_value():\n    assert value() == {assertion}\n",
    )
    assert result.status == status
    assert result.environment is not None and result.environment.pytest_version == "9.2.0"
    assert result.cases[0].definition_name == "test_value"
    assert result.cases[0].definition_start == 2
    assert not list(root.rglob("*.pyc"))


@pytest.mark.parametrize(
    "body",
    [
        "import unittest\nclass TestBad(unittest.TestCase):\n    def test_bad(self): pass\n",
        "async def test_bad(): pass\n",
        "def test_bad(subtests):\n    with subtests.test():\n        assert True\n",
    ],
)
def test_unsupported_items_never_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    result, _ = run_source(tmp_path, monkeypatch, body)
    assert result.reason == "unsupported_collection"
    assert result.status == "runner_failure"
    assert not result.cases


@pytest.mark.parametrize("addopts", ["--maxfail=1", "--collect-only", "--lf", "--stepwise"])
def test_config_effective_options_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, addopts: str
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "def test_value(): pass\n",
        extra={"pytest.ini": f"[pytest]\naddopts = {addopts}\n"},
    )
    assert result.reason == "unsupported_runner"


def test_selected_cohort_and_stable_exclusions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "import pytest\ndef test_ok(): pass\n"
        "@pytest.mark.skip\ndef test_skip(): pass\n"
        "@pytest.mark.xfail\ndef test_xfail(): assert False\n"
        "@pytest.mark.xfail\ndef test_xpass(): pass\n"
        "def test_deselect(): pass\n",
        options=("-q", "-k", "not deselect"),
    )
    assert result.status == "passed"
    assert [case.outcome for case in result.cases] == ["passed", "skipped", "xfailed", "xpassed"]
    assert result.collection is not None
    assert result.collection.deselected == ("test_module.py::test_deselect",)


def test_original_checkout_fallback_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tmp_path / "original"
    source = (
        f"import sys\nsys.path.insert(0, {str(original)!r})\nimport module\n"
        "def test_value(): assert module.value() == 2\n"
    )
    result, _ = run_source(tmp_path, monkeypatch, source)
    assert result.status == "origin_violation"


def test_collection_import_failure_is_structural(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "import nonexistent_ephorate_fixture_module\ndef test_value(): pass\n",
    )
    assert result.status == "structural_failure"


def test_structural_context_in_real_assertion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "def test_value():\n    try:\n        import nonexistent_ephorate_fixture_module\n"
        "    except ImportError:\n        raise AssertionError('hidden') from None\n",
    )
    assert result.status == "structural_failure"
    assert result.cases[0].phases[1].exception_category == "structural"


def test_custom_collection_hook_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "def test_value(): pass\n",
        extra={
            "conftest.py": "def pytest_pycollect_makeitem(collector, name, obj):\n    return None\n"
        },
    )
    assert result.reason == "unsupported_collection"


def test_timeout_kills_owned_child_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, root = run_source(
        tmp_path,
        monkeypatch,
        "import subprocess, sys, time\nfrom pathlib import Path\n"
        "def test_wait():\n"
        "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "    Path('child.pid').write_text(str(child.pid))\n"
        "    time.sleep(120)\n",
        timeout=1,
    )
    assert result.status == "timeout"
    pid = int((root / "child.pid").read_text())
    try:
        state = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], text=True, capture_output=True, check=False
        ).stdout.strip()
        assert not state or state.startswith("Z"), state
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_parent_interrupt_also_reaps_process(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True
    )
    started = time.monotonic()
    runner._terminate_group(process)
    assert process.returncode is not None
    assert time.monotonic() - started < 3


def test_invalid_unicode_cannot_escape_parser() -> None:
    events = packet()
    events[1]["definition_name"] = "\ud800"
    with pytest.raises(runner.InvalidEvidence):
        runner._decode_evidence(encoded(events), 0)


def test_limit_marker_retains_limit_reason_after_truncated_events() -> None:
    events = packet()
    events.pop(-2)
    events[-1]["error_reason"] = "evidence_limit"
    with pytest.raises(runner.InvalidEvidence, match="evidence_limit"):
        runner._decode_evidence(encoded(events), 0)


def test_interruption_propagates_only_after_child_reaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_wait = subprocess.Popen.wait
    processes: list[subprocess.Popen[bytes]] = []

    def interrupted_wait(process: subprocess.Popen[bytes], timeout: float | None = None) -> int:
        if not processes:
            processes.append(process)
            raise CheckInterrupted(signal.SIGTERM)
        return original_wait(process, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "wait", interrupted_wait)
    with pytest.raises(CheckInterrupted) as caught:
        run_source(tmp_path, monkeypatch, "def test_wait(): pass\n")
    assert caught.value.signum == signal.SIGTERM
    assert processes[0].returncode is not None


def test_preparation_deadline_is_a_trial_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exhausted(*args: object) -> dict[str, str]:
        raise EphorateError("budget_exhausted", "test fixture")

    # The runner helper normally stubs preparation, so replace its module function after setup.
    monkeypatch.setattr(units, "project_modules", exhausted)
    state = SourceState("b" * 40, "e" * 64, (), ())
    change = Change(
        tmp_path,
        tmp_path / ".git",
        tmp_path / ".git",
        "a" * 40,
        "b" * 40,
        "c" * 40,
        "d" * 40,
        (),
        state,
    )
    result = runner.run_trial(tmp_path, change, CheckConfig(tmp_path), "single", "single", (), 1)
    assert result.status == "timeout"
    assert result.reason == "timeout"


def test_plugin_provenance_is_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    one, _ = run_source(first, monkeypatch, "def test_value(): pass\n")
    two, _ = run_source(second, monkeypatch, "def test_value(): pass\n")
    assert one.environment == two.environment
    assert one.environment is not None and one.environment.plugins
    assert all(not name.isdecimal() for name, _ in one.environment.plugins)


@pytest.mark.parametrize("setting", ["log_file", "cache_dir", "addopts"])
def test_config_output_cannot_escape_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: str
) -> None:
    outside = tmp_path / "outside.txt"
    value = str(outside) if setting != "addopts" else f"--debug={outside}"
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "def test_value(): pass\n",
        extra={"pytest.ini": f"[pytest]\n{setting} = {value}\n"},
    )
    assert result.reason == "unsupported_runner"
    assert not outside.exists()


def test_namespace_locations_must_all_be_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.machinery
    import types

    original = tmp_path / "original"
    root = tmp_path / "scratch"
    root.mkdir()
    evidence = tmp_path / "evidence"
    evidence.touch()
    instance = observer.Observer(
        {
            "root": str(root),
            "original": str(original),
            "evidence": str(evidence),
            "modules": {"example": "src/example"},
            "tracked": [],
        }
    )
    namespace = types.ModuleType("example")
    spec = importlib.machinery.ModuleSpec("example", loader=None, is_package=True)
    spec.submodule_search_locations = [str(root / "src/example")]
    namespace.__spec__ = spec
    monkeypatch.setitem(sys.modules, "example", namespace)
    instance.check_origins()
    assert instance.origin_valid
    spec.submodule_search_locations.append(str(tmp_path / "external/example"))
    instance.check_origins()
    assert not instance.origin_valid


def test_ignored_dependency_under_original_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.machinery
    import types

    original = tmp_path / "original"
    root = tmp_path / "scratch"
    root.mkdir()
    evidence = tmp_path / "evidence"
    evidence.touch()
    instance = observer.Observer(
        {
            "root": str(root),
            "original": str(original),
            "evidence": str(evidence),
            "modules": {"module": "module.py"},
            "tracked": ["module.py", "test_module.py"],
        }
    )
    dependency = types.ModuleType("example_dependency")
    spec = importlib.machinery.ModuleSpec(
        "example_dependency",
        loader=None,
        origin=str(original / ".venv/site-packages/dependency.py"),
    )
    dependency.__spec__ = spec
    monkeypatch.setitem(sys.modules, "example_dependency", dependency)
    instance.check_origins()
    assert instance.origin_valid


@pytest.mark.parametrize("via_override", [False, True])
def test_junit_output_from_addopts_rejected_before_writer_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, via_override: bool
) -> None:
    outside = tmp_path / "outside.xml"
    options = ("-q", "-o", f"addopts=--junitxml={outside}") if via_override else ("-q",)
    configuration = "[pytest]\n" if via_override else f"[pytest]\naddopts=--junitxml={outside}\n"
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "def test_value(): pass\n",
        options=options,
        extra={"pytest.ini": configuration},
    )
    assert result.reason == "unsupported_runner"
    assert not outside.exists()


def test_config_cannot_select_tests_outside_scratch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "external"
    outside.mkdir()
    sentinel = tmp_path / "must-not-exist"
    (outside / "test_external.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\ndef test_external(): pass\n"
    )
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "def test_value(): pass\n",
        extra={"pytest.ini": f"[pytest]\ntestpaths={outside}\n"},
    )
    assert result.reason == "unsupported_runner"
    assert not sentinel.exists()


def test_teardown_error_is_never_an_assertion_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "import pytest\n@pytest.fixture\ndef fixture():\n    yield\n    assert False\n"
        "def test_value(fixture):\n    assert False\n",
    )
    assert result.status == "phase_failure"
    assert result.cases[0].phases[-1].when == "teardown"


def test_wrapped_substitute_has_no_claimed_definition_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, _ = run_source(
        tmp_path,
        monkeypatch,
        "from functools import wraps\n"
        "def test_claimed():\n    assert False\n"
        "@wraps(test_claimed)\ndef substitute():\n    pass\n"
        "test_claimed = substitute\n",
    )
    assert result.status == "passed"
    case = result.cases[0]
    assert case.definition_name is None
    assert case.definition_start is None
    assert case.definition_end is None


def test_ambient_temp_directory_cannot_create_inside_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = tmp_path / "original"
    monkeypatch.setattr(tempfile, "tempdir", str(original))
    original_mkdtemp = tempfile.mkdtemp
    created: list[Path] = []

    def record_directory(
        suffix: str | None = None, prefix: str | None = None, dir: str | Path | None = None
    ) -> str:
        result = original_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        created.append(Path(result).resolve())
        return result

    monkeypatch.setattr(tempfile, "mkdtemp", record_directory)
    result, _ = run_source(tmp_path, monkeypatch, "def test_value(): pass\n")
    assert result.status == "passed"
    assert created
    assert all(not path.is_relative_to(original.resolve()) for path in created)
    assert {path.name for path in original.iterdir()} == {"module.py", "test_module.py"}
