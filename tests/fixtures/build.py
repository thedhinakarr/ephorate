"""Build isolated two-commit repositories for removal-check acceptance tests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FixtureRepo:
    path: Path
    base: str
    head: str


def git(root: Path, *args: str) -> str:
    """Run fixture-only Git without machine configuration or user hooks."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_AUTHOR_NAME="Fixture Author",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_NAME="Fixture Author",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
        GIT_AUTHOR_DATE="2026-01-01T00:00:00+00:00",
        GIT_COMMITTER_DATE="2026-01-01T00:00:00+00:00",
        LC_ALL="C",
    )
    return subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            *args,
        ],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def create_repo(
    destination: Path,
    base_files: Mapping[str, str | bytes],
    head_files: Mapping[str, str | bytes],
    *,
    base_modes: Mapping[str, int] | None = None,
    head_modes: Mapping[str, int] | None = None,
) -> FixtureRepo:
    """Create only an absent/empty owned destination; never replace existing data."""
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("fixture destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    git(destination, "init", "--initial-branch=main")
    previous: set[str] = set()
    commits = []
    for label, files, modes in (
        ("base", base_files, base_modes or {}),
        ("head", head_files, head_modes or {}),
    ):
        for removed in previous - files.keys():
            (destination / removed).unlink()
        for name, content in files.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts:
                raise ValueError("fixture path must be a repository-relative file")
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode() if isinstance(content, str) else content)
            path.chmod(modes.get(name, 0o644))
        git(destination, "add", "--all")
        git(destination, "commit", "--allow-empty", "-m", label)
        commits.append(git(destination, "rev-parse", "HEAD"))
        previous = set(files)
    return FixtureRepo(destination, commits[0], commits[1])


CASES = (
    "needed_assertion",
    "untested_needed",
    "unneeded_branch",
    "prose_comment",
    "directive_comment",
    "moved_definition",
    "metadata_subject",
    "runtime_exception",
    "structural_exception",
    "wrapped_structural",
    "setup_teardown",
    "cohort_drift",
    "stable_exclusions",
    "no_tests",
    "all_skipped",
    "flaky_baseline",
    "flaky_confirmation",
    "unstable_control",
    "group_only",
    "added_module",
    "deleted_module",
    "empty_file",
    "pure_deletion_hunk",
    "rename_pair",
    "judge_overlap",
    "custom_test_names",
    "config_change",
    "idle_added_modified",
    "idle_mixed",
    "idle_bad_run",
    "idle_ambiguous",
    "cap",
    "budget",
    "timeout",
    "interrupt",
    "source_unchanged",
    "git_rejections",
    "literal_paths",
    "malformed_evidence",
    "wrong_import",
    "local_venv",
    "unsupported_items",
    "package_named_ephorate",
    "output_safety",
    "deterministic",
    "fail_on",
)


def build_case(name: str, destination: Path) -> FixtureRepo:
    if name not in CASES:
        raise ValueError(f"unknown fixture case: {name}")
    base: dict[str, str | bytes] = {
        ".gitignore": ".venv/\n__pycache__/\n.pytest_cache/\nignored-sentinel\n",
        "subject.py": "def value():\n    return 1\n",
        "tests/test_subject.py": (
            "from subject import value\n\ndef test_value():\n    assert value() == 2\n"
        ),
    }
    head = dict(base)
    head["subject.py"] = "def value():\n    return 2\n"
    head_modes: dict[str, int] = {}
    if name == "untested_needed":
        base["subject.py"] = "def value():\n    return 2\n\ndef unseen():\n    return 1\n"
        head["subject.py"] = "def value():\n    return 2\n\ndef unseen():\n    return 2\n"
    elif name == "unneeded_branch":
        base["subject.py"] = "def value():\n    return 2\n"
        head["subject.py"] = "def value():\n    if False:\n        return 99\n    return 2\n"
    elif name in {"prose_comment", "directive_comment"}:
        base["subject.py"] = "# A plain comment\ndef value():\n    return 2\n"
        comment = "# Another plain comment" if name == "prose_comment" else "# pragma: no cover"
        head["subject.py"] = comment + "\ndef value():\n    return 2\n"
    elif name == "moved_definition":
        comments = "".join(f"# Stable separator {index}\n" for index in range(10))
        base["subject.py"] = (
            "def unused():\n    return 7\n\n" + comments + "\ndef value():\n    return 2\n"
        )
        head["subject.py"] = (
            comments + "\ndef unused():\n    return 7\n\ndef value():\n    return 2\n"
        )
    elif name in {"metadata_subject", "empty_file"}:
        base["subject.py"] = head["subject.py"]
        base["empty_deleted.py"] = ""
        head["empty_added.py"] = ""
        if name == "metadata_subject":
            head_modes["subject.py"] = 0o755
            base["binary.py"] = b"\x00old"
            head["binary.py"] = b"\x00new"
    elif name in {"runtime_exception", "structural_exception", "wrapped_structural"}:
        body = {
            "runtime_exception": "    raise ValueError('sensitive runtime detail')\n",
            "structural_exception": "    return missing_name\n",
            "wrapped_structural": (
                "    try:\n        raise ImportError('sensitive import detail')\n"
                "    except ImportError:\n        raise AssertionError('hidden cause') from None\n"
            ),
        }[name]
        base["subject.py"] = "def value():\n" + body
    elif name == "setup_teardown":
        tests = (
            "import pytest\nfrom subject import value\n\n"
            "@pytest.fixture(autouse=True)\ndef guard():\n    assert value() == 2\n    yield\n\n"
            "def test_value():\n    assert value() == 2\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name == "cohort_drift":
        tests = (
            "import pytest\nfrom subject import value\n\n"
            "def test_value():\n    if value() == 1:\n        pytest.skip('changed cohort')\n"
            "    assert value() == 2\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name == "stable_exclusions":
        tests = str(base["tests/test_subject.py"]) + (
            "\nimport pytest\n\n@pytest.mark.skip(reason='stable')\n"
            "def test_skip():\n    assert False\n\n@pytest.mark.xfail(reason='stable')\n"
            "def test_xfail():\n    assert False\n\n"
            "@pytest.mark.xfail(reason='stable', strict=False)\n"
            "def test_xpass():\n    assert True\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name == "no_tests":
        del base["tests/test_subject.py"]
        del head["tests/test_subject.py"]
    elif name == "all_skipped":
        tests = (
            "import pytest\n\n@pytest.mark.skip(reason='all skipped')\ndef test_skip():\n    pass\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name in {"flaky_baseline", "flaky_confirmation", "unstable_control"}:
        state = destination.resolve().parent / (destination.name + "-counter")
        condition = {
            "flaky_baseline": "count != 2",
            "flaky_confirmation": "value() == 2 or count == 4",
            "unstable_control": "value() == 2 and count != 5",
        }[name]
        tests = (
            "from pathlib import Path\nfrom subject import value\n\n"
            "def test_value():\n"
            f"    state = Path({str(state)!r})\n"
            "    count = int(state.read_text()) + 1 if state.exists() else 1\n"
            "    state.write_text(str(count))\n"
            f"    assert {condition}\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name in {"group_only", "idle_bad_run"}:
        base["left.py"] = base["right.py"] = "VALUE = 1\n"
        head["left.py"] = head["right.py"] = "VALUE = 2\n"
        base.pop("subject.py")
        head.pop("subject.py")
        tests = (
            "import left\nimport right\n\ndef test_pair():\n"
            "    if left.VALUE != right.VALUE:\n        raise NameError('mismatched pair')\n"
            "    assert left.VALUE == 2\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
        if name == "idle_bad_run":
            head["tests/test_subject.py"] = tests + (
                "\ndef test_new():\n    if left.VALUE == 1:\n"
                "        raise ValueError('invalid idle evidence')\n    assert True\n"
            )
    elif name == "added_module":
        del base["subject.py"]
    elif name == "deleted_module":
        base["subject.py"] = head["subject.py"]
        base["unused.py"] = "VALUE = 3\n"
    elif name == "pure_deletion_hunk":
        base["subject.py"] = "def value():\n    result = 2\n    result = 1\n    return result\n"
        head["subject.py"] = "def value():\n    result = 2\n    return result\n"
    elif name == "rename_pair":
        base["subject.py"] = head["subject.py"]
        base["old_name.py"] = "VALUE = 1\n"
        head["new_name.py"] = "VALUE = 1\n"
    elif name == "judge_overlap":
        base["subject.py"] = head["subject.py"]
        head["tests/test_subject.py"] = str(base["tests/test_subject.py"]) + "\n# Judge change\n"
    elif name == "custom_test_names":
        base["subject.py"] = head["subject.py"]
        base["pytest.ini"] = "[pytest]\npython_files = check_*.py test_*.py\n"
        head["pytest.ini"] = "[pytest]\npython_files = spec_*.py test_*.py\n"
        base["check_legacy.py"] = "def test_old():\n    assert True\n"
        head["spec_new.py"] = "def test_new():\n    assert True\n"
    elif name == "config_change":
        base["subject.py"] = head["subject.py"]
        for config in ("pytest.toml", ".pytest.toml"):
            base[config] = '[pytest]\nmarkers = ["before"]\n'
            head[config] = '[pytest]\nmarkers = ["after"]\n'
        base["pyproject.toml"] = "[tool.pytest.ini_options]\n"
        head["pyproject.toml"] = '[tool.pytest.ini_options]\nmarkers = ["after"]\n'
        base["conftest.py"] = "# Before\n"
        head["conftest.py"] = "# After\n"
        base[".github/workflows/check.yml"] = "name: before\n"
        head[".github/workflows/check.yml"] = "name: after\n"
    elif name == "idle_added_modified":
        base["tests/test_subject.py"] = "def test_modified():\n    assert 1 == 1\n"
        head["tests/test_subject.py"] = (
            "def test_modified():\n    assert 2 == 2\n\ndef test_added():\n    assert True\n"
        )
    elif name == "idle_mixed":
        head["tests/test_subject.py"] = str(base["tests/test_subject.py"]) + (
            "\ndef test_added():\n    assert True\n"
        )
    elif name == "idle_ambiguous":
        head["tests/test_subject.py"] = str(base["tests/test_subject.py"]) + (
            "\ndef factory():\n    def generated():\n        assert True\n    return generated\n"
            "\ntest_generated = factory()\n"
        )
    elif name == "cap":
        base["subject.py"] = head["subject.py"]
        for index in range(51):
            base[f"unit_{index:02}.py"] = "# Before\nVALUE = 1\n"
            head[f"unit_{index:02}.py"] = "# After\nVALUE = 1\n"
        head["tests/test_subject.py"] = str(base["tests/test_subject.py"]) + (
            "\ndef test_added():\n    assert True\n"
        )
    elif name in {"timeout", "interrupt"}:
        base["subject.py"] = "def value():\n    while True:\n        pass\n"
    elif name == "literal_paths":
        base["subject.py"] = head["subject.py"]
        for path in ("with space.py", "café.py", "-leading.py", "tab\tname.py", "line\nname.py"):
            base[path] = b"VALUE = 1\r\nTAIL = 3"
            head[path] = b"VALUE = 2\r\nTAIL = 3"
    elif name == "wrong_import":
        tests = (
            "import importlib.util\nfrom pathlib import Path\n\n"
            f"original = Path({str(destination.resolve() / 'subject.py')!r})\n"
            "spec = importlib.util.spec_from_file_location('subject', original)\n"
            "subject = importlib.util.module_from_spec(spec)\n"
            "import sys\nsys.modules['subject'] = subject\nspec.loader.exec_module(subject)\n\n"
            "def test_value():\n    assert subject.value() == 2\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name == "unsupported_items":
        tests = (
            "import unittest\nfrom subject import value\n\nclass TestValue(unittest.TestCase):\n"
            "    def setUp(self):\n        assert value() == 2\n"
            "    def test_value(self):\n        assert value() == 2\n"
        )
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    elif name == "package_named_ephorate":
        base["ephorate/__init__.py"] = str(base.pop("subject.py"))
        head["ephorate/__init__.py"] = str(head.pop("subject.py"))
        tests = "from ephorate import value\n\ndef test_value():\n    assert value() == 2\n"
        base["tests/test_subject.py"] = head["tests/test_subject.py"] = tests
    return create_repo(destination, base, head, head_modes=head_modes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args()
    try:
        fixture = build_case(args.case, args.dest)
    except (ValueError, OSError, subprocess.CalledProcessError):
        parser.exit(2, "Unable to build fixture in the requested empty destination.\n")
    print(json.dumps({"base": fixture.base, "head": fixture.head}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
