"""Command-line and tracked-configuration boundary."""

import argparse
import math
import os
import signal
import sys
import time
import tomllib
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import NoReturn

from ephorate import git, tool_version
from ephorate.models import CheckConfig, CheckInterrupted, CheckReport, EphorateError
from ephorate.report import OutputTarget, write_json


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise EphorateError("configuration_error", "arguments")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="ephorate", description="Evidence from bounded change-removal trials.")
    parser.add_argument("--version", action="version", version=f"ephorate {tool_version()}")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    check = sub.add_parser(
        "check", help="check a clean committed change using trusted pytest tests"
    )
    check.add_argument("--repo", type=Path, default=Path.cwd())
    check.add_argument("--base")
    check.add_argument("--source-root", choices=(".", "src"))
    check.add_argument("--max-units", type=int)
    for name in (
        "budget-seconds",
        "baseline-timeout-seconds",
        "min-trial-timeout-seconds",
        "timeout-factor",
    ):
        check.add_argument(f"--{name}", type=float)
    check.add_argument("--fail-on")
    check.add_argument("--output", type=Path)
    return parser


def _strings(value: object, *, empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
        raise EphorateError("configuration_error", "configuration")
    if not empty and not value:
        raise EphorateError("configuration_error", "configuration")
    return tuple(str(v) for v in value)


def _number(value: object, *, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EphorateError("configuration_error", "configuration")
    if integer and not isinstance(value, int):
        raise EphorateError("configuration_error", "configuration")
    if value <= 0:
        raise EphorateError("configuration_error", "configuration")
    if integer:
        return value
    try:
        if not math.isfinite(value):
            raise EphorateError("configuration_error", "configuration")
    except OverflowError as exc:
        raise EphorateError("configuration_error", "configuration") from exc
    return value


def _command(command: Sequence[str]) -> tuple[str, ...]:
    if not command or any("\0" in arg for arg in command):
        raise EphorateError("configuration_error", "test_command")
    if command[0] == "pytest":
        args = list(command[1:])
    elif command[0] in {"python", "python3", sys.executable} and list(command[1:3]) == [
        "-m",
        "pytest",
    ]:
        args = list(command[3:])
    else:
        raise EphorateError("unsupported_runner", "test_command")
    if any(arg in {"|", "||", "&&", ";", ">", ">>", "<", "&"} for arg in args):
        raise EphorateError("configuration_error", "test_command")
    # Parsed pytest options and positional selectors are checked again by the observer.
    path_options = {
        "-c",
        "--rootdir",
        "--confcutdir",
        "--basetemp",
        "--junitxml",
        "--junit-xml",
        "--log-file",
        "--override-ini",
    }
    for i, arg in enumerate(args):
        key, separator, value = arg.partition("=")
        if key in path_options:
            candidate = value if separator else (args[i + 1] if i + 1 < len(args) else "")
            if not candidate or Path(candidate).is_absolute() or ".." in Path(candidate).parts:
                raise EphorateError("configuration_error", "test_command")
        if arg.startswith("-c/") or arg.startswith("--pyargs"):
            raise EphorateError("unsupported_runner", "test_command")
    return tuple(args)


def parse_config(argv: Sequence[str]) -> CheckConfig:
    arguments = list(argv)
    command: list[str] | None = None
    if "--" in arguments:
        boundary = arguments.index("--")
        command = arguments[boundary + 1 :]
        arguments = arguments[:boundary]
    values = _parser().parse_args(arguments)
    if sys.implementation.name != "cpython" or not (3, 11) <= sys.version_info[:2] < (3, 16):
        raise EphorateError("unsupported_runner", "interpreter")
    if sys.platform not in {"linux", "darwin"}:
        raise EphorateError("unsupported_runner", "platform")
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH", "PYTHONHOME"):
        if os.environ.get(name):
            raise EphorateError("configuration_error", f"clear_{name}_use_tracked_configuration")
    repo = git.repo_root(values.repo, time.monotonic() + 30)
    settings: dict[str, object] = {}
    try:
        path = repo / ".ephorate.toml"
        if path.exists():
            with path.open("rb") as stream:
                document = tomllib.load(stream)
            if set(document) != {"check"} or not isinstance(document["check"], dict):
                raise EphorateError("configuration_error", "configuration")
            settings = document["check"]
    except (OSError, ValueError) as exc:
        raise EphorateError("configuration_error", "configuration") from exc
    defaults: dict[str, object] = {
        "source_root": ".",
        "judge_patterns": [],
        "other_patterns": [],
        "max_units": 50,
        "budget_seconds": 900,
        "baseline_timeout_seconds": 300,
        "min_trial_timeout_seconds": 30,
        "timeout_factor": 3,
        "fail_on": [],
    }
    if set(settings) - (set(defaults) | {"test_command"}):
        raise EphorateError("configuration_error", "configuration")
    effective = defaults | settings
    for key in defaults:
        override = getattr(values, key, None)
        if override is not None:
            effective[key] = override.split(",") if key == "fail_on" else override
    source_root = effective["source_root"]
    if source_root not in (".", "src"):
        raise EphorateError("configuration_error", "source_root")
    fail_on = _strings(effective["fail_on"])
    if len(set(fail_on)) != len(fail_on) or set(fail_on) - {"loose", "unjudged", "idle"}:
        raise EphorateError("configuration_error", "fail_on")
    selected = (
        tuple(command)
        if command is not None
        else _strings(effective.get("test_command"), empty=False)
    )
    return CheckConfig(
        repo=repo,
        base_ref=values.base,
        source_root=str(source_root),
        pytest_argv=_command(selected),
        judge_patterns=_strings(effective["judge_patterns"]),
        other_patterns=_strings(effective["other_patterns"]),
        max_units=int(_number(effective["max_units"], integer=True)),
        budget_seconds=_number(effective["budget_seconds"]),
        baseline_timeout_seconds=_number(effective["baseline_timeout_seconds"]),
        min_trial_timeout_seconds=_number(effective["min_trial_timeout_seconds"]),
        timeout_factor=_number(effective["timeout_factor"]),
        fail_on=fail_on,
        output=values.output,
    )


def exit_code(report: CheckReport) -> int:
    if report.status == "failed":
        return 2
    if report.status == "interrupted":
        return 130
    requested = set(report.config.fail_on)
    return int(
        any(result.verdict in requested for result in report.units)
        or ("idle" in requested and any(r.status == "idle" for r in report.idle_tests))
    )


@contextmanager
def _finalization_deadline(seconds: float) -> Iterator[None]:
    started = time.monotonic()
    old_handler = signal.getsignal(signal.SIGALRM)
    old_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def expired(signum: int, frame: FrameType | None) -> NoReturn:
        raise EphorateError("output_error", "finalization_timeout")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0]:
            remaining = max(0.000001, old_timer[0] - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, old_timer[1])


def main(argv: Sequence[str] | None = None) -> int:
    from ephorate.engine import check

    started = time.monotonic()
    target: OutputTarget | None = None
    old_handlers: dict[int, int | Callable[[int, FrameType | None], object] | None] = {}
    caught_signal: int | None = None

    def interrupt(signum: int, frame: FrameType | None) -> None:
        nonlocal caught_signal
        caught_signal = signum
        raise CheckInterrupted(signum)

    try:
        config = parse_config(list(sys.argv[1:] if argv is None else argv))
        deadline = started + config.budget_seconds
        for signum in (signal.SIGINT, signal.SIGTERM):
            old_handlers[signum] = signal.signal(signum, interrupt)
        change = git.resolve_change(config.repo, config.base_ref, deadline)
        if config.output is not None:
            target = OutputTarget(config.output, change)
        result = check(change, config, deadline)
        with _finalization_deadline(30):
            if target is None:
                write_json(result, sys.stdout)
            else:
                target.publish(result)
                target.close()
            counts = {
                key: sum(r.verdict == key for r in result.units)
                for key in ("held", "loose", "inert", "unjudged")
            }
            summary = ", ".join(f"{count} {key}" for key, count in counts.items())
            print(f"Ephorate {result.status}: {summary}", file=sys.stderr)
        return 128 + caught_signal if caught_signal is not None else exit_code(result)
    except EphorateError as exc:
        print(f"ephorate: {exc.operation}: {exc.reason}", file=sys.stderr)
        return 2
    except CheckInterrupted as exc:
        print("ephorate: interrupted", file=sys.stderr)
        return 128 + exc.signum
    except (OSError, ValueError):
        print("ephorate: infrastructure_failure", file=sys.stderr)
        return 2
    finally:
        for saved_signal, previous in old_handlers.items():
            signal.signal(saved_signal, previous)
        if target is not None:
            target.close()
