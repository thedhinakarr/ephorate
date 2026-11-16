"""Shared setup keeps all tested repositories synthetic and outside the source checkout."""

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.fixtures.build import FixtureRepo, build_case


@pytest.fixture(autouse=True)
def explicit_runner_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH", "PYTHONHOME"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Callable[[str], FixtureRepo]:
    count = 0

    def build(name: str) -> FixtureRepo:
        nonlocal count
        count += 1
        return build_case(name, tmp_path / f"{name}-{count}")

    return build
