"""Controlled evidence tests exercise rare ordering and budget boundaries without flaky clocks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from ephorate import engine
from ephorate.models import (
    CaseResult,
    Change,
    CheckConfig,
    Collection,
    Environment,
    PhaseResult,
    TrialPurpose,
    TrialResult,
    TrialStatus,
)
from tests.fixtures.build import FixtureRepo, create_repo
from tests.test_engine import check_repo

NODE_A = "tests/test_cases.py::test_a"
NODE_B = "tests/test_cases.py::test_b"


def result(
    trial_id: str,
    purpose: TrialPurpose,
    unit_ids: tuple[str, ...],
    status: TrialStatus = "passed",
    witnesses: tuple[str, ...] = (),
) -> TrialResult:
    cases = []
    for node in (NODE_A, NODE_B):
        failed = node in witnesses
        cases.append(
            CaseResult(
                node,
                "tests/test_cases.py",
                node.split("::")[-1],
                1,
                2,
                "failed" if failed else "passed",
                (
                    PhaseResult("setup", "passed", False, "none", ()),
                    PhaseResult(
                        "call",
                        "failed" if failed else "passed",
                        False,
                        "assertion" if failed else "none",
                        ("builtins.AssertionError",) if failed else (),
                    ),
                    PhaseResult("teardown", "passed", False, "none", ()),
                ),
            )
        )
    return TrialResult(
        trial_id,
        purpose,
        unit_ids,
        status,
        None if status == "passed" else "invalid_evidence",
        0 if status == "passed" else 1,
        Collection((NODE_A, NODE_B), (), ("tests/test_cases.py",), (), False),
        tuple(cases),
        0.01,
        Environment("3.15.2", "cpython", "macos", "2.50.0", "9.2.0", ()),
    )


def repository(tmp_path: Path, names: tuple[str, ...] = ("subject",)) -> FixtureRepo:
    base = {
        "tests/test_cases.py": "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n"
    }
    base.update({name + ".py": "VALUE = 1\n" for name in names})
    head = base | {name + ".py": "VALUE = 2\n" for name in names}
    return create_repo(tmp_path / "target", base, head)


Fake = Callable[[str, TrialPurpose, tuple[str, ...]], TrialResult]


def replace_runner(monkeypatch: pytest.MonkeyPatch, fake: Fake) -> None:
    def run(
        root: Path,
        change: Change,
        config: CheckConfig,
        trial_id: str,
        purpose: TrialPurpose,
        unit_ids: tuple[str, ...],
        timeout_s: float,
    ) -> TrialResult:
        assert root != change.repo
        assert timeout_s > 0
        return fake(trial_id, purpose, unit_ids)

    monkeypatch.setattr(engine, "run_trial", run)


def test_disjoint_repeat_witnesses_are_not_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        witnesses = (NODE_A,) if purpose == "single" else (NODE_B,) if purpose == "repeat" else ()
        return result(
            identity, purpose, ids, "assertion_failure" if witnesses else "passed", witnesses
        )

    replace_runner(monkeypatch, fake)
    report = check_repo(repository(tmp_path))
    assert report.units[0].reason == "confirmation_failed"
    assert not report.units[0].witnesses
    assert report.trials[-1].purpose == "control"


def test_only_intersecting_witnesses_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        witnesses = (
            (NODE_A, NODE_B) if purpose == "single" else (NODE_B,) if purpose == "repeat" else ()
        )
        return result(
            identity, purpose, ids, "assertion_failure" if witnesses else "passed", witnesses
        )

    replace_runner(monkeypatch, fake)
    report = check_repo(repository(tmp_path))
    assert report.units[0].verdict == "held"
    assert report.units[0].witnesses == (NODE_B,)


def test_bad_later_control_invalidates_previous_behavior_but_keeps_inert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = {
        "a_held.py": "VALUE = 1\n",
        "b_loose.py": "VALUE = 1\n",
        "c_inert.py": "# Before\nVALUE = 1\n",
        "d_candidate.py": "VALUE = 1\n",
        "tests/test_cases.py": "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n",
    }
    head = base | {
        "a_held.py": "VALUE = 2\n",
        "b_loose.py": "VALUE = 2\n",
        "c_inert.py": "# After\nVALUE = 1\n",
        "d_candidate.py": "VALUE = 2\n",
    }
    singles = controls = 0

    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        nonlocal singles, controls
        if purpose == "single":
            singles += 1
        if purpose == "control":
            controls += 1
        fails = (purpose in {"single", "repeat"} and singles != 2) or (
            purpose == "control" and controls == 2
        )
        return result(
            identity,
            purpose,
            ids,
            "assertion_failure" if fails else "passed",
            (NODE_A,) if fails else (),
        )

    replace_runner(monkeypatch, fake)
    report = check_repo(create_repo(tmp_path / "target", base, head))
    assert (report.status, report.reason) == ("failed", "unstable_control")
    assert [(unit.verdict, unit.reason) for unit in report.units] == [
        ("unjudged", "unstable_control"),
        ("unjudged", "unstable_control"),
        ("inert", "ast_equivalent"),
        ("unjudged", "unstable_control"),
    ]
    assert all(not unit.witnesses for unit in report.units)
    assert not report.groups and not report.idle_tests


def test_deadline_after_successful_baselines_is_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed = 0

    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        nonlocal completed
        completed += 1
        return result(identity, purpose, ids)

    replace_runner(monkeypatch, fake)
    monkeypatch.setattr(engine._Check, "remaining", lambda self: 100 if completed < 2 else 0)
    report = check_repo(repository(tmp_path, ("a", "b")))
    assert (report.status, report.reason) == ("partial", "budget_exhausted")
    assert report.baseline.passing == (NODE_A, NODE_B)
    assert all(unit.reason == "budget_exhausted" for unit in report.units)
    assert len(report.trials) == 2


def test_unstarted_control_budget_does_not_invalidate_prior_loose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed = singles = 0

    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        nonlocal completed, singles
        completed += 1
        if purpose == "single":
            singles += 1
        fails = singles == 2 and purpose in {"single", "repeat"}
        return result(
            identity,
            purpose,
            ids,
            "assertion_failure" if fails else "passed",
            (NODE_A,) if fails else (),
        )

    replace_runner(monkeypatch, fake)
    monkeypatch.setattr(engine._Check, "remaining", lambda self: 100 if completed < 5 else 0)
    report = check_repo(repository(tmp_path, ("a", "b")))
    assert report.status == "partial"
    assert report.units[0].verdict == "loose"
    assert (report.units[1].verdict, report.units[1].reason) == ("unjudged", "budget_exhausted")
    assert not report.units[1].witnesses


@pytest.mark.parametrize(
    "status",
    [
        "invalid_evidence",
        "origin_violation",
        "structural_failure",
        "runtime_failure",
        "phase_failure",
    ],
)
def test_uncertainty_overrides_an_assertion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: TrialStatus
) -> None:
    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        if purpose != "single":
            return result(identity, purpose, ids)
        return result(identity, purpose, ids, status, (NODE_A,))

    replace_runner(monkeypatch, fake)
    report = check_repo(repository(tmp_path))
    assert report.units[0].verdict == "unjudged"
    assert not report.units[0].witnesses
    assert all(trial.purpose not in {"repeat", "control"} for trial in report.trials)


def test_deselected_case_change_overrides_assertion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(identity: str, purpose: TrialPurpose, ids: tuple[str, ...]) -> TrialResult:
        observed = (
            result(identity, purpose, ids, "assertion_failure", (NODE_A,))
            if purpose == "single"
            else result(identity, purpose, ids)
        )
        if purpose == "single":
            assert observed.collection is not None
            observed = replace(
                observed,
                collection=replace(
                    observed.collection, deselected=("tests/test_cases.py::another",)
                ),
            )
        return observed

    replace_runner(monkeypatch, fake)
    report = check_repo(repository(tmp_path))
    assert report.units[0].reason == "cohort_mismatch"
    assert not report.units[0].witnesses
