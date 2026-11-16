"""Acceptance tests run real Git snapshots and the pinned pytest observer."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from ephorate import engine, git
from ephorate.models import CheckConfig, CheckReport, EphorateError
from tests.fixtures.build import FixtureRepo, create_repo
from tests.fixtures.build import git as fixture_git

FixtureFactory = Callable[[str], FixtureRepo]


def check_repo(
    repo: FixtureRepo,
    *,
    max_units: int = 50,
    other_patterns: tuple[str, ...] = (),
    min_trial_timeout_seconds: float = 30,
    timeout_factor: float = 3,
    pytest_argv: tuple[str, ...] = ("-q",),
) -> CheckReport:
    config = CheckConfig(
        repo.path,
        base_ref=repo.base,
        max_units=max_units,
        other_patterns=other_patterns,
        min_trial_timeout_seconds=min_trial_timeout_seconds,
        timeout_factor=timeout_factor,
        pytest_argv=pytest_argv,
    )
    deadline = time.monotonic() + config.budget_seconds
    change = git.resolve_change(repo.path, repo.base, deadline)
    return engine.check(change, config, deadline)


@pytest.mark.parametrize(
    ("name", "verdict", "reason"),
    [
        ("needed_assertion", "held", "confirmed_assertion"),
        ("untested_needed", "loose", "full_suite_passed_without_unit"),
        ("unneeded_branch", "loose", "full_suite_passed_without_unit"),
        ("prose_comment", "inert", "ast_equivalent"),
        ("directive_comment", "loose", "full_suite_passed_without_unit"),
        ("runtime_exception", "unjudged", "runtime_failure"),
        ("structural_exception", "unjudged", "structural_failure"),
        ("wrapped_structural", "unjudged", "structural_failure"),
        ("setup_teardown", "unjudged", "phase_failure"),
        ("cohort_drift", "unjudged", "cohort_mismatch"),
        ("added_module", "unjudged", "structural_failure"),
        ("deleted_module", "loose", "full_suite_passed_without_unit"),
        ("pure_deletion_hunk", "held", "confirmed_assertion"),
        ("package_named_ephorate", "held", "confirmed_assertion"),
    ],
)
def test_individual_verdicts(
    fixture_repo: FixtureFactory, name: str, verdict: str, reason: str
) -> None:
    result = check_repo(fixture_repo(name))
    assert result.status == "complete", result
    assert len(result.units) == 1
    unit = result.units[0]
    assert (unit.verdict, unit.reason) == (verdict, reason)
    assert result.baseline.trial_ids == ("baseline-1", "baseline-2")
    related = [trial for trial in result.trials if unit.unit.id in trial.unit_ids]
    if verdict == "held":
        assert unit.witnesses == ("tests/test_subject.py::test_value",)
        assert [trial.purpose for trial in result.trials] == [
            "baseline",
            "baseline",
            "single",
            "repeat",
            "control",
        ]
        assert result.trials[-1].status == "passed"
        assert len(unit.trial_ids) == 3
    elif verdict == "inert":
        assert related == []
    else:
        assert not unit.witnesses


def test_structural_group_never_promotes_members(fixture_repo: FixtureFactory) -> None:
    result = check_repo(fixture_repo("group_only"))
    assert len(result.units) == 2
    assert {(unit.verdict, unit.reason) for unit in result.units} == {
        ("unjudged", "structural_failure")
    }
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.id == "structural-1"
    assert set(group.unit_ids) == {unit.unit.id for unit in result.units}
    assert group.status == "assertion_failure"
    assert group.assertion_nodes == ("tests/test_subject.py::test_pair",)
    assert all(not unit.witnesses for unit in result.units)
    assert [trial.purpose for trial in result.trials].count("group") == 1


def test_group_that_passes_still_does_not_promote(tmp_path: Path) -> None:
    test = (
        "import left, right\n\ndef test_pair():\n"
        "    if left.VALUE != right.VALUE:\n        raise NameError('pair')\n"
        "    assert left.VALUE in (1, 2)\n"
    )
    base = {"left.py": "VALUE = 1\n", "right.py": "VALUE = 1\n", "tests/test_pair.py": test}
    repo = create_repo(
        tmp_path / "pair", base, base | {"left.py": "VALUE = 2\n", "right.py": "VALUE = 2\n"}
    )
    result = check_repo(repo)
    assert result.groups[0].status == "passed"
    assert all(unit.verdict == "unjudged" for unit in result.units)


@pytest.mark.parametrize("name", ["no_tests", "all_skipped", "flaky_baseline"])
def test_invalid_baseline_stops_before_removals(fixture_repo: FixtureFactory, name: str) -> None:
    result = check_repo(fixture_repo(name))
    assert result.status == "failed"
    assert all(unit.verdict == "unjudged" for unit in result.units)
    assert all(trial.purpose == "baseline" for trial in result.trials)
    if name == "flaky_baseline":
        assert result.reason == "baseline_unstable"


def test_stable_exclusions_are_disclosed_but_not_witnesses(fixture_repo: FixtureFactory) -> None:
    result = check_repo(fixture_repo("stable_exclusions"))
    assert result.status == "complete"
    assert result.units[0].verdict == "held"
    assert {outcome for _, outcome in result.baseline.excluded} == {"skipped", "xfailed", "xpassed"}
    assert result.units[0].witnesses == ("tests/test_subject.py::test_value",)


@pytest.mark.parametrize("drift", ["added", "removed", "deselected", "xfail", "excluded"])
def test_each_cohort_drift_overrides_call_assertions(tmp_path: Path, drift: str) -> None:
    tests = (
        "import pytest\nfrom subject import value\n\ndef test_value():\n    assert value() == 2\n"
    )
    extra: dict[str, str] = {}
    if drift in {"added", "removed"}:
        condition = 1 if drift == "added" else 2
        tests += f"\nif value() == {condition}:\n    def test_extra():\n        assert True\n"
    elif drift == "deselected":
        tests += "\ndef test_extra():\n    assert True\n"
        extra["conftest.py"] = (
            "from subject import value\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    if value() == 1:\n"
            "        removed = [item for item in items if item.name == 'test_extra']\n"
            "        items[:] = [item for item in items if item not in removed]\n"
            "        config.hook.pytest_deselected(items=removed)\n"
        )
    elif drift == "xfail":
        tests += (
            "\n@pytest.mark.xfail(value() == 1, reason='conditional')\n"
            "def test_extra():\n    assert value() == 2\n"
        )
    else:
        tests += (
            "\n@pytest.mark.xfail(reason='conditional', strict=False)\n"
            "def test_extra():\n    assert value() == 1\n"
        )
    base = {"subject.py": "def value():\n    return 1\n", "tests/test_subject.py": tests} | extra
    report = check_repo(
        create_repo(tmp_path / drift, base, base | {"subject.py": "def value():\n    return 2\n"})
    )
    assert report.units[0].reason == "cohort_mismatch"
    assert not report.units[0].witnesses


def test_teardown_failure_overrides_another_call_assertion(tmp_path: Path) -> None:
    tests = (
        "import pytest\nfrom subject import value\n\n"
        "@pytest.fixture(autouse=True)\ndef guard():\n    yield\n    assert value() == 2\n\n"
        "def test_value():\n    assert value() == 2\n"
    )
    base = {"subject.py": "def value():\n    return 1\n", "tests/test_subject.py": tests}
    report = check_repo(
        create_repo(
            tmp_path / "teardown", base, base | {"subject.py": "def value():\n    return 2\n"}
        )
    )
    assert report.units[0].reason == "phase_failure"
    assert not report.units[0].witnesses


def test_fully_deselected_suite_does_not_make_every_unit_loose(
    fixture_repo: FixtureFactory,
) -> None:
    report = check_repo(fixture_repo("needed_assertion"), pytest_argv=("-q", "-k", "missing_test"))
    assert report.status == "failed"
    assert all(unit.verdict == "unjudged" for unit in report.units)


def test_confirmation_that_stops_failing_remains_unjudged(fixture_repo: FixtureFactory) -> None:
    result = check_repo(fixture_repo("flaky_confirmation"))
    assert result.status == "complete"
    assert result.units[0].reason == "confirmation_failed"
    assert not result.units[0].witnesses
    assert result.trials[-1].purpose == "control"
    assert result.trials[-1].status == "passed"


def test_executed_bad_control_aborts(fixture_repo: FixtureFactory) -> None:
    result = check_repo(fixture_repo("unstable_control"))
    assert (result.status, result.reason) == ("failed", "unstable_control")
    assert result.units[0].reason == "unstable_control"
    assert not result.units[0].witnesses
    assert not result.groups and not result.idle_tests


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("idle_added_modified", {"test_added": "idle", "test_modified": "idle"}),
        ("idle_mixed", {"test_added": "idle"}),
        ("idle_bad_run", {"test_new": "unknown"}),
        ("idle_ambiguous", {"test_generated": "unknown"}),
    ],
)
def test_idle_is_scoped_to_valid_complete_subject_reversal(
    fixture_repo: FixtureFactory, name: str, expected: dict[str, str]
) -> None:
    result = check_repo(fixture_repo(name))
    assert result.status == "complete", result.reason
    assert {case.node_id.split("::")[-1]: case.status for case in result.idle_tests} == expected
    if name == "idle_added_modified":
        assert {case.change for case in result.idle_tests} == {"added", "modified"}
    if name == "idle_mixed":
        assert (
            next(trial for trial in result.trials if trial.purpose == "idle").status
            == "assertion_failure"
        )


@pytest.mark.parametrize("wrapped", [False, True])
def test_forged_callable_name_with_a_different_source_line_has_unknown_mapping(
    tmp_path: Path,
    wrapped: bool,
) -> None:
    original = "def test_stable():\n    assert True\n"
    replaced = original + (
        "\ndef test_claimed():\n    assert True\n\n"
        "def factory():\n"
        "    def generated():\n        assert True\n"
        "    generated.__name__ = 'test_claimed'\n"
        "    generated.__qualname__ = 'test_claimed'\n"
        + ("    generated.__wrapped__ = test_claimed\n" if wrapped else "")
        + "    return generated\n\n"
        "test_claimed = factory()\n"
    )
    base = {"subject.py": "VALUE = 1\n", "tests/test_identity.py": original}
    head = base | {"subject.py": "VALUE = 2\n", "tests/test_identity.py": replaced}
    report = check_repo(create_repo(tmp_path / "forged-identity", base, head))
    candidate = next(case for case in report.idle_tests if case.node_id.endswith("::test_claimed"))
    observed = next(
        case for case in report.trials[0].cases if case.node_id.endswith("::test_claimed")
    )
    if wrapped:
        assert observed.definition_name is None
        assert observed.definition_start is None
        assert observed.definition_end is None
    else:
        assert observed.definition_name == "test_claimed"
        assert observed.definition_start != 4
    assert (candidate.change, candidate.status, candidate.reason) == (
        "unknown",
        "unknown",
        "mapping_ambiguous",
    )


def test_unit_cap_counts_inert_units_and_disables_idle_subset(fixture_repo: FixtureFactory) -> None:
    result = check_repo(fixture_repo("cap"))
    assert result.status == "partial"
    assert len(result.units) == 51
    assert all(unit.verdict == "inert" for unit in result.units[:50])
    assert (result.units[-1].verdict, result.units[-1].reason) == ("unjudged", "unit_cap")
    assert result.units[-1].unit.path == "unit_50.py"
    assert all(trial.purpose != "idle" for trial in result.trials)
    assert result.idle_tests[0].status == "unknown"


def test_mode_and_empty_subject_units_are_not_inert(fixture_repo: FixtureFactory) -> None:
    result = check_repo(fixture_repo("metadata_subject"), max_units=2)
    units = {unit.unit.path: unit for unit in result.units}
    assert units["binary.py"].unit.classification == "other"
    assert units["empty_added.py"].reason == "unsupported_change"
    assert units["empty_deleted.py"].reason == "unsupported_change"
    assert units["subject.py"].reason == "unit_cap"
    assert all(unit.verdict == "unjudged" for unit in result.units)
    assert result.status == "partial"


@pytest.mark.parametrize("name", ["judge_overlap", "custom_test_names", "config_change"])
def test_changed_judges_are_visible_and_never_reversed(
    fixture_repo: FixtureFactory, name: str
) -> None:
    result = check_repo(fixture_repo(name), other_patterns=("tests/*",))
    assert result.status == "complete", result.reason
    assert result.change.files
    assert all(file.classification == "judge" for file in result.change.files)
    assert not result.units
    assert not any(trial.purpose in {"single", "repeat", "control"} for trial in result.trials)


def source_bytes(repo: FixtureRepo) -> tuple[dict[str, bytes], bytes, str, str]:
    files = {
        str(path.relative_to(repo.path)): path.read_bytes()
        for path in repo.path.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(repo.path).parts
    }
    return (
        files,
        (repo.path / ".git/index").read_bytes(),
        fixture_git(repo.path, "show-ref"),
        fixture_git(repo.path, "rev-parse", "HEAD"),
    )


@pytest.mark.parametrize("name", ["needed_assertion", "runtime_exception", "timeout"])
def test_source_bytes_index_refs_and_ignored_sentinel_survive(
    fixture_repo: FixtureFactory, name: str
) -> None:
    repo = fixture_repo(name)
    (repo.path / "ignored-sentinel").write_bytes(b"do not touch\x00\xff")
    before = source_bytes(repo)
    result = check_repo(
        repo,
        min_trial_timeout_seconds=0.5 if name == "timeout" else 30,
        timeout_factor=0.001 if name == "timeout" else 3,
    )
    if name == "timeout":
        assert result.units[0].reason == "timeout"
    assert source_bytes(repo) == before


def test_untracked_file_rejection_preserves_all_bytes(fixture_repo: FixtureFactory) -> None:
    repo = fixture_repo("source_unchanged")
    (repo.path / "untracked-sentinel").write_bytes(b"not yours")
    before = source_bytes(repo)
    with pytest.raises(EphorateError):
        check_repo(repo)
    assert source_bytes(repo) == before


def test_fixture_builder_refuses_to_overwrite(fixture_repo: FixtureFactory) -> None:
    repo = fixture_repo("needed_assertion")
    before = source_bytes(repo)
    with pytest.raises(ValueError, match="empty"):
        create_repo(repo.path, {}, {})
    assert source_bytes(repo) == before
