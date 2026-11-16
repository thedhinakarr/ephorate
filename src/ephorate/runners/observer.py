"""Structured pytest observer loaded by path, without importing the tool package."""

import inspect
import json
import os
import platform
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

MAX_BYTES = 16 * 1024 * 1024
MAX_CASES = 100_000
MAX_STRING = 16 * 1024
STRUCTURAL = (ImportError, NameError, AttributeError, SyntaxError)
COLLECT_HOOKS = (
    "pytest_collect_file",
    "pytest_collect_directory",
    "pytest_pycollect_makemodule",
    "pytest_pycollect_makeitem",
)


def exception_evidence(error: BaseException | None) -> tuple[str, tuple[str, ...]]:
    """Inspect suppressed context too: wrapping an import error cannot witness a removal."""
    if error is None:
        return "none", ()
    pending = [(error, 0)]
    seen: set[int] = set()
    names: set[str] = set()
    structural = False
    nonassertion = False
    truncated = False
    while pending:
        current, depth = pending.pop()
        if id(current) in seen:
            continue
        if len(seen) >= 64 or depth > 16:
            truncated = True
            continue
        seen.add(id(current))
        cls = type(current)
        names.add(f"{cls.__module__}.{cls.__qualname__}")
        structural |= isinstance(current, STRUCTURAL)
        nonassertion |= not isinstance(current, (AssertionError, pytest.fail.Exception))
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append((linked, depth + 1))
        if isinstance(current, BaseExceptionGroup):
            pending.extend((member, depth + 1) for member in current.exceptions)
    category = (
        "structural"
        if structural
        else "unknown"
        if truncated
        else "runtime"
        if nonassertion
        else "assertion"
    )
    return category, tuple(sorted(names))


class Observer:
    def __init__(self, manifest: dict[str, Any]) -> None:
        self.root = Path(manifest["root"]).resolve()
        self.original = Path(manifest["original"]).resolve()
        self.evidence = Path(manifest["evidence"])
        self.expected: dict[str, str] = manifest["modules"]
        self.original_paths = {(self.original / path).resolve() for path in manifest["tracked"]}
        self.items: list[dict[str, Any]] = []
        self.judges: set[str] = set()
        self.skipped: set[str] = set()
        self.deselected: list[str] = []
        self.collection_error = False
        self.started = False
        self.collected = False
        self.finished = False
        self.origin_valid = True
        self.reason: str | None = None
        self.config: pytest.Config | None = None
        self.bytes_written = 0
        self.buffered_bytes = 0

    def fail(self, reason: str) -> None:
        if self.reason is None:
            self.reason = reason

    def relative(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except (OSError, ValueError):
            self.fail("unsupported_collection")
            return None

    def write(self, event: dict[str, Any]) -> None:
        def safe(value: object) -> bool:
            if isinstance(value, str):
                return len(value.encode("utf-8")) <= MAX_STRING
            if isinstance(value, dict):
                return all(safe(key) and safe(item) for key, item in value.items())
            if isinstance(value, list):
                return all(safe(item) for item in value)
            return True

        if not safe(event):
            self.fail("evidence_limit")
            return
        payload = json.dumps(event, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
        encoded = payload.encode("utf-8")
        limit = MAX_BYTES if event.get("event") == "finish" else MAX_BYTES - 1024
        if self.bytes_written + len(encoded) > limit:
            self.fail("evidence_limit")
            return
        with self.evidence.open("ab") as stream:
            stream.write(encoded)
        self.bytes_written += len(encoded)

    def plugins(self) -> list[list[str | None]]:
        if self.config is None:
            return []
        manager = self.config.pluginmanager
        versions = {
            id(plugin): (dist.project_name, dist.version)
            for plugin, dist in manager.list_plugin_distinfo()
        }
        result: set[tuple[str, str | None]] = set()
        for _name, plugin in manager.list_name_plugin():
            if plugin is None or plugin is self:
                continue
            origin = getattr(plugin, "__file__", None)
            if isinstance(origin, str):
                path = Path(origin).resolve()
                if path.is_relative_to(self.root):
                    relative = path.relative_to(self.root).as_posix()
                    self.judges.add(relative)
                    result.add(("local:" + relative, None))
                    continue
            if id(plugin) in versions:
                project, version = versions[id(plugin)]
                result.add((project, version))
                continue
            # Registered conftest names can be absolute; only publish stable module identities.
            module = getattr(plugin, "__name__", type(plugin).__module__)
            if isinstance(module, str) and module.startswith("_pytest."):
                result.add((module, pytest.__version__))
        return [[name, version] for name, version in sorted(result)]

    def supported(self) -> bool:
        if self.config is None:
            return False
        option = self.config.option
        forbidden = (
            "collectonly",
            "setuponly",
            "setupplan",
            "usepdb",
            "trace",
            "maxfail",
            "lf",
            "failedfirst",
            "newfirst",
            "stepwise",
            "stepwise_skip",
            "stepwise_reset",
            "numprocesses",
            "looponfail",
            "reruns",
            "count",
            "continue_on_collection_errors",
        )
        if any(getattr(option, name, False) for name in forbidden):
            self.fail("unsupported_runner")
        if getattr(option, "dist", "no") != "no":
            self.fail("unsupported_runner")
        manager = self.config.pluginmanager
        for name, plugin in manager.list_name_plugin():
            module = getattr(plugin, "__name__", type(plugin).__module__)
            if any(
                part in str(name).lower() or part in str(module).lower()
                for part in ("xdist", "rerunfailures", "flaky", "pytest_repeat")
            ):
                self.fail("unsupported_runner")
        for hook in COLLECT_HOOKS:
            for implementation in getattr(manager.hook, hook).get_hookimpls():
                if implementation.plugin is self:
                    continue
                if not implementation.function.__module__.startswith("_pytest."):
                    self.fail("unsupported_collection")
        return self.reason is None

    def check_origins(self) -> None:
        for name, module in tuple(sys.modules.items()):
            if module is None:
                continue
            spec = getattr(module, "__spec__", None)
            origin = getattr(spec, "origin", None) or getattr(module, "__file__", None)
            resolved: Path | None = None
            if isinstance(origin, str) and origin not in ("built-in", "frozen"):
                try:
                    resolved = Path(origin).resolve()
                except (OSError, ValueError):
                    self.origin_valid = False
            if resolved in self.original_paths:
                self.origin_valid = False
            if name not in self.expected:
                continue
            expected = (self.root / self.expected[name]).resolve()
            if resolved is not None:
                if resolved != expected:
                    self.origin_valid = False
            else:
                locations = getattr(spec, "submodule_search_locations", None)
                if locations is None:
                    self.origin_valid = False
                else:
                    paths = [Path(path).resolve() for path in locations]
                    if not paths or any(path != expected for path in paths):
                        self.origin_valid = False
        if not self.origin_valid:
            self.fail("origin_violation")

    def validate_paths(self, config: pytest.Config, option: Any) -> None:
        def inside(value: str | Path) -> None:
            raw = os.path.expandvars(os.path.expanduser(str(value).split("::", 1)[0]))
            path = Path(raw)
            if ".." in path.parts or not (self.root / path).resolve().is_relative_to(self.root):
                self.fail("unsupported_runner")

        inside(config.rootpath)
        if config.inipath is not None:
            inside(config.inipath)
        for value in getattr(option, "file_or_dir", ()):
            inside(value)
        for name in (
            "rootdir",
            "inifilename",
            "confcutdir",
            "basetemp",
            "xmlpath",
            "log_file",
            "debug",
        ):
            value = getattr(option, name, None)
            if value:
                inside(value)
        for value in getattr(option, "ignore", ()) or ():
            inside(value)
        for name in ("cache_dir", "log_file"):
            value = config.getini(name)
            if value:
                inside(value)
        for name in ("pythonpath", "testpaths"):
            for value in config.getini(name):
                inside(value)
        if getattr(option, "pyargs", False):
            self.fail("unsupported_runner")
        if self.reason is not None:
            raise pytest.UsageError(self.reason)

    @pytest.hookimpl(tryfirst=True)
    def pytest_load_initial_conftests(self, early_config: pytest.Config) -> None:
        self.config = early_config
        self.validate_paths(early_config, early_config.known_args_namespace)

    @pytest.hookimpl(tryfirst=True)
    def pytest_configure(self, config: pytest.Config) -> None:
        self.config = config
        self.validate_paths(config, config.option)
        self.supported()

    def pytest_sessionstart(self, session: pytest.Session) -> None:
        self.check_origins()

    def pytest_itemcollected(self, item: pytest.Item) -> None:
        if len(self.items) >= MAX_CASES:
            self.fail("evidence_limit")
            pytest.exit("evidence_limit", returncode=4)
        path = self.relative(item.path)
        if path is None:
            return
        self.judges.add(path)
        definition: str | None = None
        start: int | None = None
        end: int | None = None
        if type(item) is not pytest.Function:
            self.fail("unsupported_collection")
        else:
            actual = item.obj
            function = inspect.unwrap(actual)
            if inspect.iscoroutinefunction(function) or inspect.isasyncgenfunction(function):
                self.fail("unsupported_collection")
            if "subtests" in item.fixturenames:
                self.fail("unsupported_collection")
            actual_code = getattr(actual, "__code__", None)
            if actual_code is not None and actual_code is getattr(function, "__code__", None):
                try:
                    lines, start = inspect.getsourcelines(function)
                    end = start + len(lines) - 1
                    definition = function.__qualname__
                except (OSError, TypeError, AttributeError):
                    pass
        item_record = {
            "event": "item",
            "node_id": item.nodeid,
            "path": path,
            "definition_name": definition,
            "definition_start": start,
            "definition_end": end,
        }
        self.buffered_bytes += len(json.dumps(item_record, ensure_ascii=True).encode("utf-8"))
        if self.buffered_bytes > MAX_BYTES - 4096:
            self.fail("evidence_limit")
            pytest.exit("evidence_limit", returncode=4)
        self.items.append(item_record)

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        self.deselected.extend(item.nodeid for item in items)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.failed:
            self.collection_error = True
        if report.skipped:
            path = report.nodeid.split("::", 1)[0]
            relative = self.relative(self.root / path)
            if relative is not None:
                self.skipped.add(relative)
                self.judges.add(relative)

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        plugins = self.plugins()
        self.write(
            {
                "event": "start",
                "protocol": 1,
                "python_version": platform.python_version(),
                "pytest_version": pytest.__version__,
                "supported_options": self.supported(),
                "plugins": plugins,
            }
        )
        for item in self.items:
            self.write(item)

    @pytest.hookimpl(trylast=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.check_origins()
        self.start()
        self.collected = True
        self.write(
            {
                "event": "collection",
                "selected": [item.nodeid for item in session.items],
                "deselected": sorted(self.deselected),
                "judge_files": sorted(self.judges),
                "skipped_paths": sorted(self.skipped),
                "collection_error": self.collection_error,
            }
        )
        if self.reason is not None:
            pytest.exit(self.reason, returncode=4)

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, pytest.TestReport, pytest.TestReport]:
        before = exception_evidence(call.excinfo.value if call.excinfo is not None else None)
        report = yield
        after = exception_evidence(call.excinfo.value if call.excinfo is not None else None)
        categories = {before[0], after[0]}
        category = next(
            (
                value
                for value in ("structural", "unknown", "runtime", "assertion")
                if value in categories
            ),
            "none",
        )
        if report.failed and category == "none":
            category = "unknown"
        if call.when != "call" and category == "assertion":
            category = "runtime"
        types = sorted(set(before[1]) | set(after[1]))
        self.write(
            {
                "event": "phase",
                "node_id": item.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "was_xfail": hasattr(report, "wasxfail"),
                "exception_category": category,
                "exception_types": types,
            }
        )
        return report

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if type(report) is not pytest.TestReport:
            self.fail("unsupported_collection")

    def pytest_runtest_logfinish(self, nodeid: str, location: tuple[str, int | None, str]) -> None:
        self.check_origins()
        if self.reason == "evidence_limit":
            pytest.exit("evidence_limit", returncode=4)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self.ensure_finished(int(exitstatus))

    def ensure_finished(self, exit_code: int) -> None:
        if self.finished:
            return
        self.check_origins()
        self.start()
        if not self.collected:
            self.write(
                {
                    "event": "collection",
                    "selected": [],
                    "deselected": [],
                    "judge_files": sorted(self.judges),
                    "skipped_paths": sorted(self.skipped),
                    "collection_error": self.collection_error,
                }
            )
        self.write(
            {
                "event": "finish",
                "exit_code": exit_code,
                "origin_valid": self.origin_valid,
                "error_reason": self.reason,
            }
        )
        self.finished = True
