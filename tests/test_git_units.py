"""Real local repositories exercise the source/trial trust boundary."""

from __future__ import annotations

import shlex
import time
from dataclasses import replace
from pathlib import Path

import pytest

from ephorate import git, units
from ephorate.models import Change, CheckConfig, EphorateError
from tests.fixtures.build import FixtureRepo, build_case, create_repo
from tests.fixtures.build import git as fixture_git


def deadline() -> float:
    return time.monotonic() + 60


def load(fixture: FixtureRepo, config: CheckConfig | None = None) -> tuple[Change, CheckConfig]:
    config = config or CheckConfig(repo=fixture.path)
    change = git.resolve_change(fixture.path, fixture.base, deadline())
    return units.classify_change(change, config, deadline()), config


def test_independent_clone_and_exact_single_reversal(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    change, config = load(fixture)
    selected = units.split_change(change, config, deadline())
    assert len(selected) == 1
    assert selected[0].kind == "hunk"
    source_index = (fixture.path / ".git/index").read_bytes()
    with git.snapshot(change, deadline()) as scratch:
        assert not (scratch / ".git/objects/info/alternates").exists()
        assert fixture_git(scratch, "remote") == ""
        assert fixture_git(scratch, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
        assert fixture_git(scratch, "rev-parse", "HEAD") == fixture.head
        git.apply_units(scratch, change, selected, deadline())
        assert (scratch / "subject.py").read_text() == "def value():\n    return 1\n"
        assert (fixture.path / "subject.py").read_text() == "def value():\n    return 2\n"
    assert not scratch.exists()
    assert (fixture.path / ".git/index").read_bytes() == source_index
    git.verify_source_unchanged(change, deadline())


def test_multiple_hunks_revert_exactly_together_and_separately(tmp_path: Path) -> None:
    old = "a = 1\nkeep = 10\nmore = 20\nb = 2\n"
    new = "a = 3\nkeep = 10\nmore = 20\nb = 4\n"
    fixture = create_repo(tmp_path / "target", {"subject.py": old}, {"subject.py": new})
    change, config = load(fixture)
    selected = units.split_change(change, config, deadline())
    assert len(selected) == 2
    with git.snapshot(change, deadline()) as scratch:
        git.apply_units(scratch, change, selected[:1], deadline())
        assert (scratch / "subject.py").read_text() == "a = 1\nkeep = 10\nmore = 20\nb = 4\n"
    with git.snapshot(change, deadline()) as scratch:
        git.apply_units(scratch, change, selected, deadline())
        assert (scratch / "subject.py").read_text() == old


@pytest.mark.parametrize("case", ["added_module", "deleted_module", "pure_deletion_hunk"])
def test_file_existence_and_deletion_reversals(tmp_path: Path, case: str) -> None:
    fixture = build_case(case, tmp_path / "target")
    change, config = load(fixture)
    selected = tuple(
        unit
        for unit in units.split_change(change, config, deadline())
        if units.unit_is_supported(change, unit)
    )
    assert selected
    expected = git.expected_bytes(change, selected, deadline())
    with git.snapshot(change, deadline()) as scratch:
        git.apply_units(scratch, change, selected, deadline())
        for path, content in expected.items():
            if content is None:
                assert not (scratch / path).exists()
            else:
                assert (scratch / path).read_bytes() == content


@pytest.mark.parametrize("case,expected", [("prose_comment", True), ("directive_comment", False)])
def test_ast_comment_policy(tmp_path: Path, case: str, expected: bool) -> None:
    fixture = build_case(case, tmp_path / "target")
    change, config = load(fixture)
    selected = units.split_change(change, config, deadline())
    assert len(selected) == 1
    assert units.is_inert(change, selected[0], deadline()) is expected


def test_ast_is_per_unit_not_whole_change(tmp_path: Path) -> None:
    fixture = build_case("moved_definition", tmp_path / "target")
    change, config = load(fixture)
    selected = units.split_change(change, config, deadline())
    assert len(selected) >= 2
    assert not any(units.is_inert(change, unit, deadline()) for unit in selected)


def test_metadata_and_empty_subjects_are_not_inert(tmp_path: Path) -> None:
    fixture = build_case("metadata_subject", tmp_path / "target")
    change, config = load(fixture)
    by_path = {item.path: item for item in change.files}
    assert by_path["binary.py"].classification == "other"
    for path in ("subject.py", "empty_added.py", "empty_deleted.py"):
        assert by_path[path].classification == "subject"
        assert by_path[path].reason == "unsupported_change"
    selected = units.split_change(change, config, deadline())
    assert all(unit.kind == "file" for unit in selected)
    assert not any(units.is_inert(change, unit, deadline()) for unit in selected)


def test_judges_win_exclusions_and_preserve_base_custom_tests(tmp_path: Path) -> None:
    fixture = create_repo(
        tmp_path / "target",
        {
            "pytest.toml": '[pytest]\npython_files=["check_*.py"]\n',
            "check_deleted.py": "def custom_case():\n    assert True\n",
            "subject.py": "answer = 1\n",
        },
        {"pytest.toml": '[pytest]\npython_files=["spec_*.py"]\n', "subject.py": "answer = 2\n"},
    )
    change, config = load(fixture, CheckConfig(fixture.path, other_patterns=("*",)))
    by_path = {item.path: item for item in change.files}
    assert by_path["check_deleted.py"].classification == "judge"
    assert by_path["pytest.toml"].classification == "judge"
    assert by_path["subject.py"].classification == "other"
    assert {unit.path for unit in units.split_change(change, config, deadline())} == {"subject.py"}


def test_discovery_protects_nonstandard_test_file(tmp_path: Path) -> None:
    fixture = create_repo(tmp_path / "target", {"custom.py": "x = 1\n"}, {"custom.py": "x = 2\n"})
    change, config = load(fixture)
    assert change.files[0].classification == "subject"
    final = units.classify_change(change, config, deadline(), ("custom.py",))
    assert final.files[0].classification == "judge"
    assert units.split_change(final, config, deadline()) == ()


def test_dirty_and_untracked_repositories_rejected(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    (fixture.path / "untracked").write_text("private detail")
    with pytest.raises(EphorateError, match="unsafe_repository") as caught:
        git.resolve_change(fixture.path, fixture.base, deadline())
    assert "private detail" not in str(caught.value)


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_index_flags_rejected(tmp_path: Path, flag: str) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    fixture_git(fixture.path, "update-index", flag, "subject.py")
    with pytest.raises(EphorateError, match="unsafe_repository"):
        git.resolve_change(fixture.path, fixture.base, deadline())


def test_filter_is_rejected_before_it_can_execute(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    marker = tmp_path / "filter-ran"
    fixture_git(fixture.path, "config", "filter.bad.clean", f"touch {marker}")
    with pytest.raises(EphorateError, match="unsafe_repository"):
        git.resolve_change(fixture.path, fixture.base, deadline())
    assert not marker.exists()


@pytest.mark.parametrize("attribute", ["filter=bad", "working-tree-encoding=UTF-16", "ident"])
def test_checkout_attributes_rejected(tmp_path: Path, attribute: str) -> None:
    fixture = create_repo(
        tmp_path / "target",
        {"subject.py": "value = 1\n"},
        {"subject.py": "value = 2\n"},
    )
    # info/attributes is read without modifying the committed worktree.
    (fixture.path / ".git/info/attributes").write_text(f"subject.py {attribute}\n")
    with pytest.raises(EphorateError, match="unsafe_repository"):
        git.resolve_change(fixture.path, fixture.base, deadline())


def test_tracked_symlink_rejected(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    (fixture.path / "link.py").symlink_to("subject.py")
    fixture_git(fixture.path, "add", "link.py")
    fixture_git(fixture.path, "commit", "-m", "symlink")
    with pytest.raises(EphorateError, match="unsafe_repository"):
        git.resolve_change(fixture.path, fixture.base, deadline())


def test_source_changes_detected_without_restoring_them(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    change, _ = load(fixture)
    (fixture.path / "subject.py").write_text("owner edit\n")
    with pytest.raises(EphorateError, match="source_changed"):
        git.verify_source_unchanged(change, deadline())
    assert (fixture.path / "subject.py").read_text() == "owner edit\n"


def test_source_cannot_be_patch_destination(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    change, config = load(fixture)
    with pytest.raises(EphorateError, match="patch_failed"):
        git.apply_units(
            fixture.path, change, units.split_change(change, config, deadline()), deadline()
        )
    git.verify_source_unchanged(change, deadline())


def test_literal_paths_and_line_endings_round_trip(tmp_path: Path) -> None:
    names = ["space name.py", "unicodé.py", "-leading.py", "tab\tname.py", "line\nname.py"]
    fixture = create_repo(
        tmp_path / "target",
        {name: b"value = 1\r\nlast = 2" for name in names},
        {name: b"value = 3\r\nlast = 2" for name in names},
    )
    change, config = load(fixture)
    # Test the lower-level byte/path boundary even for non-importable module names.
    change = replace(
        change,
        files=tuple(replace(item, classification="subject", reason=None) for item in change.files),
    )
    selected = units.split_change(change, config, deadline())
    assert len(selected) == len(names)
    with git.snapshot(change, deadline()) as scratch:
        git.apply_units(scratch, change, selected, deadline())
        for name in names:
            assert (scratch / name).read_bytes() == b"value = 1\r\nlast = 2"
    git.verify_source_unchanged(change, deadline())


def test_module_collision_is_not_silently_resolved(tmp_path: Path) -> None:
    fixture = create_repo(
        tmp_path / "target",
        {"thing.py": "x = 1\n", "thing/__init__.py": "x = 1\n"},
        {"thing.py": "x = 2\n", "thing/__init__.py": "x = 1\n"},
    )
    change, config = load(fixture)
    with pytest.raises(EphorateError, match="unsupported_module"):
        units.project_modules(change, config, deadline())


def test_missing_default_branch_does_not_guess(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    with pytest.raises(EphorateError, match="missing_ref"):
        git.resolve_change(fixture.path, None, deadline())


def test_deadline_prevents_git_execution(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    with pytest.raises(EphorateError, match="budget_exhausted"):
        git.resolve_change(fixture.path, fixture.base, time.monotonic() - 1)


def test_final_verification_rejects_new_filter_before_status(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    change, _ = load(fixture)
    marker = tmp_path / "filter-executed"
    fixture_git(
        fixture.path,
        "config",
        "filter.injected.clean",
        f"touch {shlex.quote(str(marker))}; cat",
    )
    (fixture.path / ".git/info/attributes").write_text("subject.py filter=injected\n")
    subject = fixture.path / "subject.py"
    subject.write_bytes(subject.read_bytes())  # Refresh stat data without changing the bytes.
    with pytest.raises(EphorateError, match="source_changed"):
        git.verify_source_unchanged(change, deadline())
    assert not marker.exists()


def test_live_worktree_attributes_checked_before_initial_status(tmp_path: Path) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    (fixture.path / ".gitattributes").write_text("subject.py ident\n")
    with pytest.raises(EphorateError) as caught:
        git.resolve_change(fixture.path, fixture.base, deadline())
    assert caught.value.reason == "unsafe_repository"
    assert caught.value.operation == "checkout_attribute"


@pytest.mark.parametrize("variant", ["shallow", "partial", "alternates", "submodule", "sparse"])
def test_remaining_unsupported_git_states_preserve_fixture(tmp_path: Path, variant: str) -> None:
    fixture = build_case("needed_assertion", tmp_path / "target")
    if variant == "shallow":
        (fixture.path / ".git/shallow").write_text(fixture.head + "\n")
    elif variant == "partial":
        fixture_git(fixture.path, "config", "extensions.partialClone", "origin")
        fixture_git(fixture.path, "config", "remote.origin.promisor", "true")
    elif variant == "alternates":
        alternate_objects = tmp_path / "alternate-objects"
        alternate_objects.mkdir()
        (fixture.path / ".git/objects/info/alternates").write_text(str(alternate_objects) + "\n")
    elif variant == "submodule":
        fixture_git(
            fixture.path,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{fixture.head},dependency",
        )
        fixture_git(fixture.path, "commit", "-m", "synthetic gitlink")
    elif variant == "sparse":
        fixture_git(fixture.path, "config", "core.sparseCheckout", "true")

    def file_bytes() -> dict[str, bytes]:
        return {
            path.relative_to(fixture.path).as_posix(): path.read_bytes()
            for path in fixture.path.rglob("*")
            if path.is_file()
        }

    before = file_bytes()
    with pytest.raises(EphorateError, match="unsafe_repository"):
        git.resolve_change(fixture.path, fixture.base, deadline())
    assert file_bytes() == before


def test_rename_pair_stays_visible_as_independent_delete_and_add(tmp_path: Path) -> None:
    fixture = build_case("rename_pair", tmp_path / "target")
    change, config = load(fixture)
    assert {item.path: item.status for item in change.files} == {
        "new_name.py": "A",
        "old_name.py": "D",
    }
    selected = units.split_change(change, config, deadline())
    assert {unit.path: unit.kind for unit in selected} == {
        "new_name.py": "add_file",
        "old_name.py": "delete_file",
    }
    for unit in selected:
        assert units.unit_is_supported(change, unit)
        with git.snapshot(change, deadline()) as scratch:
            git.apply_units(scratch, change, (unit,), deadline())
            if unit.kind == "add_file":
                assert not (scratch / "new_name.py").exists()
                assert not (scratch / "old_name.py").exists()
            else:
                assert (scratch / "old_name.py").read_text() == "VALUE = 1\n"
                assert (scratch / "new_name.py").read_text() == "VALUE = 1\n"
    git.verify_source_unchanged(change, deadline())
