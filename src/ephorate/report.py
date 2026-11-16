"""The public report deliberately excludes paths, patches and raw command arguments."""

import hashlib
import json
import os
import secrets
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

from ephorate import tool_version
from ephorate.models import Change, CheckReport, EphorateError


def _hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def as_dict(report: CheckReport) -> dict[str, object]:
    config = report.config
    effective: dict[str, object] = {
        "source_root": config.source_root,
        "judge_patterns": list(config.judge_patterns),
        "other_patterns": list(config.other_patterns),
        "max_units": config.max_units,
        "budget_seconds": config.budget_seconds,
        "baseline_timeout_seconds": config.baseline_timeout_seconds,
        "min_trial_timeout_seconds": config.min_trial_timeout_seconds,
        "timeout_factor": config.timeout_factor,
        "fail_on": list(config.fail_on),
        "invocation": ["<python>", "-m", "pytest"],
        "command_sha256": _hash(config.pytest_argv),
    }
    effective["effective_config_sha256"] = _hash(effective)
    unit_counts = dict.fromkeys(("held", "loose", "inert", "unjudged"), 0)
    line_counts = unit_counts.copy()
    unknown: list[str] = []
    unit_records: list[dict[str, object]] = []
    for result in report.units:
        record = asdict(result.unit)
        del record["patch"]
        record.update(
            verdict=result.verdict,
            reason=result.reason,
            witnesses=list(result.witnesses),
            trial_ids=list(result.trial_ids),
            group_ids=list(result.group_ids),
        )
        unit_records.append(record)
        unit_counts[result.verdict] += 1
        if result.unit.additions is None or result.unit.deletions is None:
            unknown.append(result.unit.id)
        elif result.unit.classification == "subject":
            line_counts[result.verdict] += result.unit.additions + result.unit.deletions
    trials: list[dict[str, object]] = []
    for trial in report.trials:
        record = asdict(trial)
        del record["duration_s"]
        del record["environment"]
        trials.append(record)
    environment = asdict(report.environment)
    environment["plugins"] = (
        None
        if report.environment.plugins is None
        else [{"name": name, "version": version} for name, version in report.environment.plugins]
    )
    change = report.change
    return {
        "schema_version": 1,
        "tool": {"name": "ephorate", "version": tool_version()},
        "environment": environment,
        "change": {
            "base_sha": change.base_sha,
            "head_sha": change.head_sha,
            "base_tree": change.base_tree,
            "head_tree": change.head_tree,
            "files": [asdict(file) for file in change.files],
        },
        "config": effective,
        "status": report.status,
        "reason": report.reason,
        "baseline": {
            "trial_ids": list(report.baseline.trial_ids),
            "passing": list(report.baseline.passing),
            "excluded": [
                {"node_id": node, "outcome": outcome} for node, outcome in report.baseline.excluded
            ],
        },
        "units": unit_records,
        "trials": trials,
        "groups": [asdict(group) for group in report.groups],
        "idle_tests": [asdict(case) for case in report.idle_tests],
        "reading_list": {
            "unit_ids": [r.unit.id for r in report.units if r.verdict in {"loose", "unjudged"}],
            "group_ids": [g.id for g in report.groups],
            "idle_node_ids": [r.node_id for r in report.idle_tests if r.status == "idle"],
            "judge_paths": [f.path for f in change.files if f.classification == "judge"],
        },
        "counts": {
            "units": unit_counts,
            "subject_lines": line_counts,
            "unknown_line_unit_ids": unknown,
        },
        "timings": {
            "total_s": report.total_duration_s,
            "trials": {t.id: t.duration_s for t in report.trials},
        },
    }


def _serialize(report: CheckReport) -> str:
    return json.dumps(as_dict(report), sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"


def write_json(report: CheckReport, stream: TextIO) -> None:
    try:
        stream.write(_serialize(report))
        stream.flush()
    except (OSError, ValueError) as exc:
        raise EphorateError("output_error", "write_report") from exc


class OutputTarget:
    """Keep the validated parent open so a path swap cannot redirect publication."""

    def __init__(self, destination: Path, change: Change) -> None:
        self.fd = -1
        self.name = destination.name
        try:
            parent = destination.parent.resolve(strict=True)
            if (
                not self.name
                or self.name in {".", ".."}
                or any(
                    parent.is_relative_to(p.resolve())
                    for p in (change.repo, change.git_dir, change.common_dir)
                )
            ):
                raise EphorateError("output_error", "validate_destination")
            identity = parent.stat()
            self.fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            opened = os.fstat(self.fd)
            if (identity.st_dev, identity.st_ino) != (opened.st_dev, opened.st_ino):
                raise EphorateError("output_error", "validate_destination")
            try:
                os.stat(self.name, dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise EphorateError("output_error", "validate_destination")
        except (OSError, ValueError) as exc:
            self.close()
            raise EphorateError("output_error", "validate_destination") from exc
        except BaseException:
            self.close()
            raise

    def publish(self, report: CheckReport) -> None:
        temporary = ".ephorate-" + secrets.token_hex(16) + ".tmp"
        created = False
        try:
            contents = _serialize(report).encode("utf-8")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=self.fd)
            created = True
            with os.fdopen(fd, "wb") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(
                temporary,
                self.name,
                src_dir_fd=self.fd,
                dst_dir_fd=self.fd,
                follow_symlinks=False,
            )
            os.fsync(self.fd)
        except (OSError, ValueError) as exc:
            raise EphorateError("output_error", "publish_report") from exc
        finally:
            if created:
                os.unlink(temporary, dir_fd=self.fd)

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def write_exclusive(report: CheckReport, destination: Path) -> None:
    target = OutputTarget(destination, report.change)
    try:
        target.publish(report)
    finally:
        target.close()
