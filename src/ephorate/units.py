"""Conservative judge classification and exact zero-context change units."""

from __future__ import annotations

import ast
import configparser
import fnmatch
import hashlib
import io
import json
import re
import tokenize
import tomllib
from collections.abc import Sequence
from dataclasses import replace
from pathlib import PurePosixPath
from typing import cast

from ephorate import git
from ephorate.models import Change, CheckConfig, EphorateError, FileChange, Unit, UnitKind

_CONFIG_FILES = {
    "pytest.toml",
    ".pytest.toml",
    "pytest.ini",
    ".pytest.ini",
    "pyproject.toml",
    "tox.ini",
    "setup.cfg",
    ".ephorate.toml",
}
_EXCLUDED_DIRS = {"migrations", "generated", "vendor", "vendored"}
_HUNK = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n", re.MULTILINE)
_DIRECTIVE = re.compile(
    r"\b(?:pragma|noqa|type|pylint|pyright|mypy|fmt|ruff|coverage|coding|encoding|doctest)\b",
    re.IGNORECASE,
)


def module_name(path: str, source_root: str) -> str | None:
    relative = PurePosixPath(path)
    if source_root != ".":
        try:
            relative = relative.relative_to(source_root)
        except ValueError:
            return None
    if relative.suffix != ".py":
        return None
    components = list(relative.with_suffix("").parts)
    if components and components[-1] == "__init__":
        components.pop()
    if not components or not all(part.isidentifier() for part in components):
        return None
    return ".".join(components)


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _python_patterns(contents: bytes, filename: str) -> tuple[str, ...]:
    tables: list[dict[str, object]] = []
    try:
        text = contents.decode("utf-8-sig")
        if filename.endswith(".toml"):
            data = tomllib.loads(text)
            if filename == "pyproject.toml":
                pytest_table = _mapping(_mapping(data.get("tool")).get("pytest"))
                tables = [pytest_table, _mapping(pytest_table.get("ini_options"))]
            elif filename in {"pytest.toml", ".pytest.toml"}:
                tables = [_mapping(data.get("pytest"))]
        else:
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(text)
            section = "tool:pytest" if filename == "setup.cfg" else "pytest"
            if parser.has_section(section):
                tables = [dict(parser.items(section))]
        patterns: list[str] = []
        for table in tables:
            if "python_files" not in table:
                continue
            value = table["python_files"]
            if isinstance(value, str):
                patterns.extend(value.split())
            elif isinstance(value, list) and all(isinstance(item, str) and item for item in value):
                patterns.extend(cast(list[str], value))
            else:
                raise EphorateError("configuration_error", "python_files")
        return tuple(patterns)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, configparser.Error):
        raise EphorateError("configuration_error", "pytest_configuration") from None


def _contexts(
    change: Change, deadline: float
) -> tuple[dict[str, git.TreeEntry], dict[str, git.TreeEntry], tuple[str, ...], dict[str, bytes]]:
    base = git.read_tree(change.repo, change.base_sha, deadline)
    head = git.read_tree(change.repo, change.head_sha, deadline)
    cache: dict[str, bytes] = {}
    patterns = {"test_*.py", "*_test.py"}
    for tree in (base, head):
        for path, entry in tree.items():
            name = PurePosixPath(path).name
            if name in _CONFIG_FILES - {".ephorate.toml"}:
                if entry.blob not in cache:
                    cache[entry.blob] = git.read_blob(change.repo, entry.blob, deadline)
                patterns.update(_python_patterns(cache[entry.blob], name))
    return base, head, tuple(sorted(patterns)), cache


def _contents(
    change: Change, entry: git.TreeEntry | None, cache: dict[str, bytes], deadline: float
) -> bytes:
    if entry is None:
        return b""
    if entry.blob not in cache:
        cache[entry.blob] = git.read_blob(change.repo, entry.blob, deadline)
    return cache[entry.blob]


def _ast_judge(contents: bytes) -> tuple[bool, bool]:
    try:
        tree = ast.parse(contents, type_comments=True)
    except (SyntaxError, ValueError, UnicodeError):
        return False, False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            return True, True
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("Test"):
                return True, True
            if any(
                (isinstance(base, ast.Name) and base.id == "TestCase")
                or (isinstance(base, ast.Attribute) and base.attr == "TestCase")
                for base in node.bases
            ):
                return True, True
    return False, True


def _classify(
    item: FileChange,
    config: CheckConfig,
    patterns: Sequence[str],
    base: bytes,
    head: bytes,
    discovered: set[str],
) -> FileChange:
    path = PurePosixPath(item.path)
    if (
        item.path in discovered
        or any(part in {"test", "tests"} for part in path.parts[:-1])
        or path.name == "conftest.py"
        or path.name in _CONFIG_FILES
        or item.path.startswith(".github/workflows/")
        or any(fnmatch.fnmatchcase(item.path, pattern) for pattern in config.judge_patterns)
        or any(fnmatch.fnmatchcase(path.name, pattern) for pattern in patterns)
    ):
        return replace(item, classification="judge", reason="judge_protected")
    base_judge, base_parsed = _ast_judge(base) if path.suffix == ".py" else (False, True)
    head_judge, _ = _ast_judge(head) if path.suffix == ".py" else (False, True)
    if base_judge or head_judge:
        return replace(item, classification="judge", reason="judge_protected")
    if any(part in _EXCLUDED_DIRS for part in path.parts[:-1]) or any(
        fnmatch.fnmatchcase(item.path, pattern) for pattern in config.other_patterns
    ):
        return replace(item, classification="other", reason="excluded_pattern")
    if (
        path.suffix != ".py"
        or b"\0" in base
        or b"\0" in head
        or item.status == "T"
        or any(
            mode is not None and mode not in {"100644", "100755"}
            for mode in (item.base_mode, item.head_mode)
        )
    ):
        return replace(item, classification="other", reason="unsupported_file")
    if config.source_root != "." and not path.is_relative_to(config.source_root):
        return replace(item, classification="other", reason="source_root_mismatch")
    if item.status == "D" and not base_parsed:
        return replace(item, classification="other", reason="ambiguous_judge")
    if module_name(item.path, config.source_root) is None:
        return replace(item, classification="subject", reason="unsupported_module")
    if (
        (item.status == "M" and item.base_mode != item.head_mode)
        or (item.status == "A" and not head)
        or (item.status == "D" and not base)
        or (item.additions == 0 and item.deletions == 0)
    ):
        return replace(item, classification="subject", reason="unsupported_change")
    return replace(item, classification="subject", reason=None)


def classify_change(
    change: Change,
    config: CheckConfig,
    deadline: float,
    discovered_judges: Sequence[str] = (),
) -> Change:
    base, head, patterns, cache = _contexts(change, deadline)
    discovered = set(discovered_judges)
    return replace(
        change,
        files=tuple(
            _classify(
                item,
                config,
                patterns,
                _contents(change, base.get(item.path), cache, deadline),
                _contents(change, head.get(item.path), cache, deadline),
                discovered,
            )
            for item in change.files
        ),
    )


def project_modules(change: Change, config: CheckConfig, deadline: float) -> dict[str, str]:
    base, head, patterns, cache = _contexts(change, deadline)
    known_judges = {item.path for item in change.files if item.classification == "judge"}
    known_other = {item.path for item in change.files if item.classification == "other"}
    result: dict[str, str] = {}
    for path in sorted(base.keys() | head.keys(), key=lambda value: value.encode("utf-8")):
        if not path.endswith(".py") or path in known_other:
            continue
        old, new = base.get(path), head.get(path)
        old_data = _contents(change, old, cache, deadline)
        new_data = _contents(change, new, cache, deadline)
        provisional = FileChange(
            path,
            "M" if old and new else "A" if new else "D",
            old.blob if old else None,
            new.blob if new else None,
            old.mode if old else None,
            new.mode if new else None,
            "other",
            None,
            1,
            1,
        )
        classified = _classify(provisional, config, patterns, old_data, new_data, known_judges)
        if classified.classification != "subject":
            continue
        name = module_name(path, config.source_root)
        if name is not None:
            if name in result and result[name] != path:
                raise EphorateError("unsupported_module", "module_collision")
            result[name] = path
    return result


def _unit(
    item: FileChange,
    kind: UnitKind,
    ordinal: int,
    ranges: tuple[int, int, int, int],
    patch: bytes,
    additions: int | None,
    deletions: int | None,
) -> Unit:
    identity = json.dumps(
        [
            1,
            item.path,
            kind,
            ordinal,
            item.base_blob,
            item.head_blob,
            hashlib.sha256(patch).hexdigest(),
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return Unit(
        hashlib.sha256(identity).hexdigest(),
        item.path,
        kind,
        ordinal,
        *ranges,
        additions,
        deletions,
        patch,
        item.classification,
    )


def split_change(change: Change, config: CheckConfig, deadline: float) -> tuple[Unit, ...]:
    del config  # Classification is explicit and finalized by classify_change.
    result: list[Unit] = []
    for item in change.files:
        if item.classification == "judge":
            continue
        base = git.read_blob(change.repo, item.base_blob, deadline)
        head = git.read_blob(change.repo, item.head_blob, deadline)
        base_count, head_count = len(git.lines(base)), len(git.lines(head))
        ranges = (1 if base_count else 0, base_count, 1 if head_count else 0, head_count)
        if item.classification != "subject" or item.reason is not None:
            result.append(_unit(item, "file", 0, ranges, b"", item.additions, item.deletions))
            continue
        patch = git.patch_for_path(change, item.path, deadline)
        if item.status in {"A", "D"}:
            kind: UnitKind = "add_file" if item.status == "A" else "delete_file"
            result.append(_unit(item, kind, 0, ranges, patch, item.additions, item.deletions))
            continue
        matches = list(_HUNK.finditer(patch))
        if not matches:
            result.append(_unit(item, "file", 0, ranges, b"", item.additions, item.deletions))
            continue
        header = patch[: matches[0].start()]
        for ordinal, match in enumerate(matches):
            base_start = int(match[1])
            old_count = int(match[2]) if match[2] is not None else 1
            head_start = int(match[3])
            new_count = int(match[4]) if match[4] is not None else 1
            end = matches[ordinal + 1].start() if ordinal + 1 < len(matches) else len(patch)
            unit_patch = header + patch[match.start() : end]
            result.append(
                _unit(
                    item,
                    "hunk",
                    ordinal,
                    (base_start, old_count, head_start, new_count),
                    unit_patch,
                    new_count,
                    old_count,
                )
            )
    return tuple(
        sorted(
            result,
            key=lambda value: (
                value.path.encode("utf-8"),
                value.base_start,
                value.head_start,
                value.ordinal,
            ),
        )
    )


def unit_is_supported(change: Change, unit: Unit) -> bool:
    return (
        unit.classification == "subject"
        and unit.kind != "file"
        and bool(unit.patch)
        and any(
            item.path == unit.path and item.classification == "subject" and item.reason is None
            for item in change.files
        )
    )


def _comments(contents: bytes) -> list[tuple[int, str]]:
    return [
        (token.start[0], token.string)
        for token in tokenize.tokenize(io.BytesIO(contents).readline)
        if token.type == tokenize.COMMENT
    ]


def _plain_comment(line: int, text: str) -> bool:
    if line <= 2 and (text.startswith("#!") or re.search(r"coding[:=]", text)):
        return False
    if _DIRECTIVE.search(text):
        return False
    if text == "#":
        return True
    if len(text) < 2 or not text[1].isspace():
        return False
    return all(character.isalnum() or character in " ,.'-" for character in text[1:])


def is_inert(change: Change, unit: Unit, deadline: float) -> bool:
    if unit.kind != "hunk" or not unit_is_supported(change, unit):
        return False
    item = next(item for item in change.files if item.path == unit.path)
    if item.status != "M" or item.base_mode != item.head_mode:
        return False
    head = git.read_blob(change.repo, item.head_blob, deadline)
    reverted = git.expected_bytes(change, (unit,), deadline)[unit.path]
    if reverted is None:
        return False
    try:
        # Only comments in the changed unit need the stricter directive exclusion.
        base = git.read_blob(change.repo, item.base_blob, deadline)
        old_start = unit.base_start if unit.base_count else 0
        new_start = unit.head_start if unit.head_count else 0
        changed_comments = [
            (line, text)
            for line, text in _comments(base)
            if unit.base_count and old_start <= line < old_start + unit.base_count
        ] + [
            (line, text)
            for line, text in _comments(head)
            if unit.head_count and new_start <= line < new_start + unit.head_count
        ]
        if any(not _plain_comment(line, text) for line, text in changed_comments):
            return False
        left = ast.parse(head, type_comments=True)
        right = ast.parse(reverted, type_comments=True)
        return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)
    except (SyntaxError, ValueError, UnicodeError, tokenize.TokenError, IndentationError):
        return False
