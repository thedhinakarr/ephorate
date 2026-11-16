"""Isolated child entry point; deliberately never imports ephorate."""

import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    manifest: dict[str, Any] = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    evidence = Path(manifest["evidence"])
    try:
        import pytest
    except ImportError:
        pytest = None  # type: ignore[assignment]
    if pytest is None or pytest.__version__ != "9.2.0":
        events = [
            {
                "event": "start",
                "protocol": 1,
                "python_version": platform.python_version(),
                "pytest_version": None if pytest is None else pytest.__version__,
                "supported_options": False,
                "plugins": [],
            },
            {
                "event": "collection",
                "selected": [],
                "deselected": [],
                "judge_files": [],
                "skipped_paths": [],
                "collection_error": False,
            },
            {
                "event": "finish",
                "exit_code": 4,
                "origin_valid": True,
                "error_reason": "unsupported_runner",
            },
        ]
        evidence.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        return 4
    spec = importlib.util.spec_from_file_location("_ephorate_observer", manifest["observer"])
    if spec is None or spec.loader is None:
        return 3
    module = importlib.util.module_from_spec(spec)
    sys.modules["_ephorate_observer"] = module
    spec.loader.exec_module(module)
    observer = module.Observer(manifest)
    root = Path(manifest["root"])
    paths = [str(root / manifest["source_root"]), str(root)]
    sys.path[:0] = list(dict.fromkeys(paths))
    exit_code = 3
    try:
        exit_code = int(pytest.main(manifest["argv"], plugins=[observer]))
    finally:
        observer.ensure_finished(exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
