"""Public CLI/report shape, privacy and exclusive-output contracts."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ephorate import cli, report
from ephorate.models import CheckReport, EphorateError
from tests.fixtures.build import FixtureRepo, build_case, create_repo
from tests.test_engine import check_repo, source_bytes

FixtureFactory = Callable[[str], FixtureRepo]


@pytest.fixture(scope="module")
def held_report(tmp_path_factory: pytest.TempPathFactory) -> CheckReport:
    return check_repo(build_case("needed_assertion", tmp_path_factory.mktemp("report") / "target"))


def document(result: CheckReport) -> dict[str, Any]:
    stream = io.StringIO()
    report.write_json(result, stream)
    decoded: dict[str, Any] = json.loads(stream.getvalue())
    assert (
        stream.getvalue()
        == json.dumps(decoded, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    )
    return decoded


def assert_schema(value: Any, schema: dict[str, Any], root: dict[str, Any]) -> None:
    """Exercise the JSON Schema vocabulary used by this fixed contract, without a dependency."""
    if "$ref" in schema:
        assert_schema(value, root["$defs"][schema["$ref"].split("/")[-1]], root)
        return
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                assert_schema(value, branch, root)
                return
            except AssertionError:
                continue
        raise AssertionError(f"no nullable branch accepted {value!r}")
    if "const" in schema:
        assert value == schema["const"]
    if "enum" in schema:
        assert value in schema["enum"]
    kind = schema.get("type")
    if kind == "object":
        assert isinstance(value, dict)
        assert set(schema.get("required", [])) <= value.keys()
        properties = schema.get("properties", {})
        if schema["additionalProperties"] is False:
            assert value.keys() <= properties.keys()
        for key, child in value.items():
            assert_schema(child, properties.get(key, schema["additionalProperties"]), root)
    elif kind == "array":
        assert isinstance(value, list)
        for child in value:
            assert_schema(child, schema["items"], root)
        if schema.get("uniqueItems"):
            assert len({json.dumps(child, sort_keys=True) for child in value}) == len(value)
    elif kind in {"integer", "number"}:
        assert not isinstance(value, bool)
        assert isinstance(value, int if kind == "integer" else (int, float))
        assert math.isfinite(value)
        if "minimum" in schema:
            assert value >= schema["minimum"]
        if "exclusiveMinimum" in schema:
            assert value > schema["exclusiveMinimum"]
    elif kind == "string":
        assert isinstance(value, str)
        if "pattern" in schema:
            import re

            assert re.fullmatch(schema["pattern"], value)
    elif kind == "boolean":
        assert isinstance(value, bool)
    elif kind == "null":
        assert value is None


def test_exact_report_schema_and_references(held_report: CheckReport) -> None:
    data = document(held_report)
    schema = json.loads((Path(__file__).parents[1] / "docs/report-v1.schema.json").read_text())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert_schema(data, schema, schema)
    units = {unit["id"] for unit in data["units"]}
    trials = {trial["id"] for trial in data["trials"]}
    groups = {group["id"] for group in data["groups"]}
    assert len(units) == len(data["units"])
    assert len(trials) == len(data["trials"])
    assert set(data["baseline"]["trial_ids"]) <= trials
    assert set(data["timings"]["trials"]) == trials
    for unit in data["units"]:
        assert set(unit["trial_ids"]) <= trials
        assert set(unit["group_ids"]) <= groups
    for trial in data["trials"]:
        assert set(trial["unit_ids"]) <= units
    assert data["counts"]["units"] == {"held": 1, "loose": 0, "inert": 0, "unjudged": 0}
    assert data["counts"]["subject_lines"]["held"] == 2
    assert not data["reading_list"]["unit_ids"]
    assert data["environment"]["pytest_version"] == "9.2.0"
    assert data["environment"]["plugins"] is not None


def test_schema_rejects_extra_keys_and_unknown_verdict(held_report: CheckReport) -> None:
    schema = json.loads((Path(__file__).parents[1] / "docs/report-v1.schema.json").read_text())
    data = document(held_report)
    data["units"][0]["raw_patch"] = "secret"
    with pytest.raises(AssertionError):
        assert_schema(data, schema, schema)
    del data["units"][0]["raw_patch"]
    data["units"][0]["verdict"] = "safe"
    with pytest.raises(AssertionError):
        assert_schema(data, schema, schema)


def test_report_omits_paths_raw_arguments_and_source(held_report: CheckReport) -> None:
    secret = "private-token-DO-NOT-PRINT"
    result = replace(held_report, config=replace(held_report.config, pytest_argv=("-k", secret)))
    data = document(result)
    text = json.dumps(data)
    assert secret not in text
    assert str(held_report.change.repo) not in text
    assert "return 2" not in text and "patch" not in data["units"][0]
    assert "source_state" not in data["change"]
    assert data["config"]["invocation"] == ["<python>", "-m", "pytest"]
    assert (
        data["config"]["command_sha256"]
        == hashlib.sha256(
            json.dumps(["-k", secret], sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
        ).hexdigest()
    )
    assert all("duration_s" not in trial for trial in data["trials"])


def test_deterministic_reports_except_timings(fixture_repo: FixtureFactory) -> None:
    repo = fixture_repo("deterministic")
    first, second = document(check_repo(repo)), document(check_repo(repo))
    first.pop("timings")
    second.pop("timings")
    assert first == second


def test_exclusive_output_never_replaces_existing_data(
    held_report: CheckReport, tmp_path: Path
) -> None:
    target = tmp_path / "report.json"
    report.write_exclusive(held_report, target)
    assert target.stat().st_mode & 0o777 == 0o600
    original = target.read_bytes()
    with pytest.raises(EphorateError, match="output_error"):
        report.write_exclusive(held_report, target)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob(".ephorate-*.tmp"))


def test_output_dangling_symlink_inside_repo_and_race(
    held_report: CheckReport, tmp_path: Path
) -> None:
    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "absent")
    with pytest.raises(EphorateError, match="output_error"):
        report.write_exclusive(held_report, dangling)
    with pytest.raises(EphorateError, match="output_error"):
        report.write_exclusive(held_report, held_report.change.repo / "result.json")
    target = tmp_path / "raced.json"
    opened = report.OutputTarget(target, held_report.change)
    target.write_bytes(b"won the race")
    try:
        with pytest.raises(EphorateError, match="output_error"):
            opened.publish(held_report)
    finally:
        opened.close()
    assert target.read_bytes() == b"won the race"
    assert dangling.is_symlink()
    assert not list(tmp_path.glob(".ephorate-*.tmp"))


def test_broken_output_stream_is_a_safe_boundary_error(held_report: CheckReport) -> None:
    stream = io.StringIO()
    stream.close()
    with pytest.raises(EphorateError, match="output_error"):
        report.write_json(held_report, stream)


@pytest.mark.parametrize(
    "command",
    [
        ["pytest", "-q"],
        ["python", "-m", "pytest", "-q"],
        ["python3", "-m", "pytest", "-q"],
        [sys.executable, "-m", "pytest", "-q"],
    ],
)
def test_supported_commands_normalize(fixture_repo: FixtureFactory, command: list[str]) -> None:
    repo = fixture_repo("needed_assertion")
    config = cli.parse_config(
        ["check", "--repo", str(repo.path), "--base", repo.base, "--", *command]
    )
    assert config.pytest_argv == ("-q",)
    assert config.repo == repo.path


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["check"],
        ["check", "--fail-on", ""],
        ["check", "--max-units", "0"],
        ["check", "--max-units", "1.5"],
        ["check", "--budget-seconds", "nan"],
        ["check", "--timeout-factor", "inf"],
        ["check", "--fail-on", "held"],
        ["check", "--fail-on", "loose,loose"],
    ],
)
def test_invalid_cli_is_exit_two_without_report(
    fixture_repo: FixtureFactory,
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = fixture_repo("needed_assertion")
    monkeypatch.chdir(repo.path)
    assert cli.main(arguments) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "content",
    [
        '[check]\nmax_units = true\ntest_command = ["pytest"]\n',
        '[check]\nmax_units = 1.5\ntest_command = ["pytest"]\n',
        '[check]\nbudget_seconds = nan\ntest_command = ["pytest"]\n',
        '[check]\nunknown = 1\ntest_command = ["pytest"]\n',
        '[check]\ntest_command = "pytest -q"\n',
        "[check]\ntest_command = []\n",
        '[check]\njudge_patterns = "tests/*"\ntest_command = ["pytest"]\n',
        '[check]\nfail_on = ["loose", "loose"]\ntest_command = ["pytest"]\n',
        '[check]\ntest_command = ["pytest"]\n[extra]\nx = 1\n',
    ],
)
def test_invalid_toml_is_rejected(fixture_repo: FixtureFactory, content: str) -> None:
    repo = fixture_repo("needed_assertion")
    (repo.path / ".ephorate.toml").write_text(content)
    with pytest.raises(EphorateError, match="configuration_error"):
        cli.parse_config(["check", "--repo", str(repo.path)])


@pytest.mark.parametrize(
    "setting",
    [
        "check = []",
        "check = 3",
        "check = true",
        '[check]\nsource_root = ["src"]',
        '[check]\nmax_units = "2"',
        "[check]\nbudget_seconds = [2]",
        "[check]\ntimeout_factor = false",
        '[check]\nfail_on = [["loose"]]',
        "[check]\njudge_patterns = [false]",
    ],
)
def test_malformed_config_shapes_are_safe_usage_failures(
    fixture_repo: FixtureFactory, setting: str, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = fixture_repo("needed_assertion")
    (repo.path / ".ephorate.toml").write_text(setting + "\n")
    assert cli.main(["check", "--repo", str(repo.path), "--", "pytest", "-q"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "configuration_error" in captured.err
    assert "Traceback" not in captured.err


def test_positive_integer_unit_cap_has_no_floating_point_upper_bound(
    fixture_repo: FixtureFactory,
) -> None:
    repo = fixture_repo("needed_assertion")
    huge = 10**400
    (repo.path / ".ephorate.toml").write_text(
        f'[check]\nmax_units = {huge}\ntest_command = ["pytest", "-q"]\n'
    )
    config = cli.parse_config(["check", "--repo", str(repo.path)])
    assert config.max_units == huge


@pytest.mark.parametrize(
    "field",
    ["budget_seconds", "baseline_timeout_seconds", "min_trial_timeout_seconds", "timeout_factor"],
)
def test_unrepresentable_timing_values_fail_without_traceback(
    fixture_repo: FixtureFactory, field: str, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = fixture_repo("needed_assertion")
    (repo.path / ".ephorate.toml").write_text(f"[check]\n{field} = {10**400}\n")
    assert cli.main(["check", "--repo", str(repo.path), "--", "pytest", "-q"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "configuration_error" in captured.err
    assert "Traceback" not in captured.err


def test_cli_overrides_target_configuration(fixture_repo: FixtureFactory) -> None:
    repo = fixture_repo("needed_assertion")
    (repo.path / ".ephorate.toml").write_text(
        '[check]\ntest_command = ["pytest", "-k", "old"]\nmax_units = 3\n'
        'budget_seconds = 10\nfail_on = ["unjudged"]\n'
    )
    config = cli.parse_config(
        [
            "check",
            "--repo",
            str(repo.path / "tests"),
            "--max-units",
            "7",
            "--fail-on",
            "loose",
            "--",
            "pytest",
            "-k",
            "new",
        ]
    )
    assert config.max_units == 7 and config.budget_seconds == 10
    assert config.fail_on == ("loose",)
    assert config.pytest_argv == ("-k", "new")


@pytest.mark.parametrize("key", ["PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH", "PYTHONHOME"])
def test_ambient_runner_configuration_is_rejected_without_values(
    fixture_repo: FixtureFactory,
    key: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = fixture_repo("needed_assertion")
    secret = "sensitive-environment-value"
    monkeypatch.setenv(key, secret)
    assert cli.main(["check", "--repo", str(repo.path), "--", "pytest"]) == 2
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert not captured.out


@pytest.mark.parametrize(
    "command",
    [
        ["sh", "-c", "pytest"],
        ["uv", "run", "pytest"],
        ["pytest", "|", "cat"],
        ["pytest", "-c", "/tmp/private-config"],
        ["pytest", "--junitxml=/tmp/private.xml"],
        ["pytest", "nul\0value"],
    ],
)
def test_unsafe_runner_commands_are_rejected(
    fixture_repo: FixtureFactory, command: list[str]
) -> None:
    repo = fixture_repo("needed_assertion")
    with pytest.raises(EphorateError):
        cli.parse_config(["check", "--repo", str(repo.path), "--", *command])


@pytest.mark.parametrize(
    ("name", "policy", "expected"),
    [
        ("untested_needed", "loose", 1),
        ("needed_assertion", "loose", 0),
        ("runtime_exception", "unjudged", 1),
        ("idle_mixed", "idle", 1),
        ("no_tests", "unjudged", 2),
    ],
)
def test_cli_fail_on_and_json_stdout(
    fixture_repo: FixtureFactory,
    name: str,
    policy: str,
    expected: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = fixture_repo(name)
    assert (
        cli.main(
            [
                "check",
                "--repo",
                str(repo.path),
                "--base",
                repo.base,
                "--fail-on",
                policy,
                "--",
                "pytest",
                "-q",
            ]
        )
        == expected
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["schema_version"] == 1
    assert "Traceback" not in captured.err


def test_cli_file_output_keeps_stdout_empty(
    fixture_repo: FixtureFactory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = fixture_repo("output_safety")
    target = tmp_path / "report.json"
    assert (
        cli.main(
            [
                "check",
                "--repo",
                str(repo.path),
                "--base",
                repo.base,
                "--output",
                str(target),
                "--",
                "pytest",
                "-q",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == ""
    assert json.loads(target.read_text())["counts"]["units"]["held"] == 1


def test_cli_src_layout_imports_the_reversed_scratch_package(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = {
        "src/example/__init__.py": "def value():\n    return 1\n",
        "tests/test_example.py": (
            "from example import value\n\ndef test_value():\n    assert value() == 2\n"
        ),
    }
    repo = create_repo(
        tmp_path / "src-layout",
        base,
        base | {"src/example/__init__.py": "def value():\n    return 2\n"},
    )
    assert (
        cli.main(
            [
                "check",
                "--repo",
                str(repo.path),
                "--base",
                repo.base,
                "--source-root",
                "src",
                "--",
                "pytest",
                "-q",
            ]
        )
        == 0
    )
    data = json.loads(capsys.readouterr().out)
    assert data["config"]["source_root"] == "src"
    assert len(data["units"]) == 1
    assert data["units"][0]["path"] == "src/example/__init__.py"
    assert data["units"][0]["verdict"] == "held"
    assert data["units"][0]["witnesses"] == ["tests/test_example.py::test_value"]


@pytest.mark.parametrize(("signum", "expected"), [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_cli_interrupt_report_and_source_preservation(
    tmp_path: Path, signum: int, expected: int
) -> None:
    marker = tmp_path / "trial-started"
    base = {
        ".gitignore": "ignored-sentinel\n",
        "subject.py": "from pathlib import Path\n\ndef value():\n"
        f"    Path({str(marker)!r}).write_text('started')\n"
        "    while True:\n        pass\n",
        "tests/test_subject.py": (
            "from subject import value\n\ndef test_value():\n    assert value() == 2\n"
        ),
    }
    repo = create_repo(
        tmp_path / "interrupted",
        base,
        base | {"subject.py": "from pathlib import Path\n\ndef value():\n    return 2\n"},
    )
    (repo.path / "ignored-sentinel").write_bytes(b"preserved")
    before = source_bytes(repo)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "ephorate",
            "check",
            "--repo",
            str(repo.path),
            "--base",
            repo.base,
            "--",
            "pytest",
            "-q",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        until = time.monotonic() + 20
        while not marker.exists() and process.poll() is None and time.monotonic() < until:
            time.sleep(0.02)
        assert marker.exists(), "removal trial did not start"
        os.kill(process.pid, signum)
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == expected, stderr
        data = json.loads(stdout)
        assert data["status"] == "interrupted"
        assert not any(unit["verdict"] == "held" for unit in data["units"])
        assert "Traceback" not in stderr
        assert source_bytes(repo) == before
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
