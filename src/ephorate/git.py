"""Read-only source inspection and independent, owned Git trial checkouts."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ephorate.models import Change, EphorateError, FileChange, Reason, SourceState, Unit

_REGULAR_MODES = {"100644", "100755"}
_DIFF_OPTIONS = (
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-renames",
    "--diff-algorithm=myers",
    "--no-indent-heuristic",
    "--inter-hunk-context=0",
    "--full-index",
    "--binary",
    "-U0",
)


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: str
    blob: str


def _root_hint(path: Path) -> Path:
    path = path.resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return path


def _temp_parent(excluded: Sequence[Path]) -> Path:
    for candidate in (Path("/tmp"), Path("/var/tmp")):
        candidate = candidate.resolve()
        if candidate.is_dir() and not any(candidate.is_relative_to(p.resolve()) for p in excluded):
            return candidate
    raise EphorateError("unsafe_repository", "temporary_directory")


def _environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_ATTR_NOSYSTEM="1",
        GIT_OPTIONAL_LOCKS="0",
        GIT_NO_LAZY_FETCH="1",
        GIT_NO_REPLACE_OBJECTS="1",
        GIT_ALLOW_PROTOCOL="file",
        GIT_LITERAL_PATHSPECS="1",
        GIT_TERMINAL_PROMPT="0",
        LC_ALL="C",
    )
    return env


def _stop(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()


def _run(
    repo: Path,
    args: Sequence[str],
    deadline: float,
    *,
    data: bytes | None = None,
    ceiling: float = 30,
    reason: Reason = "infrastructure_failure",
    accepted: tuple[int, ...] = (0,),
) -> tuple[bytes, int]:
    remaining = min(ceiling, deadline - time.monotonic())
    if remaining <= 0:
        raise EphorateError("budget_exhausted", "git")
    parent = _temp_parent((_root_hint(repo),))
    try:
        with tempfile.TemporaryDirectory(prefix="ephorate-hooks-", dir=parent) as empty:
            command = ["git"]
            for setting in (
                f"core.hooksPath={empty}",
                "core.fsmonitor=false",
                f"core.attributesFile={os.devnull}",
                "core.autocrlf=false",
                "core.eol=lf",
                "gc.auto=0",
                "maintenance.auto=false",
            ):
                command.extend(("-c", setting))
            command.extend(("-C", str(repo), *args))
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=_environment(),
                start_new_session=True,
            )
            try:
                result, _ = process.communicate(data, timeout=remaining)
            except subprocess.TimeoutExpired:
                _stop(process)
                raise EphorateError(
                    "budget_exhausted" if time.monotonic() >= deadline else reason,
                    "git_timeout",
                ) from None
            except BaseException:
                _stop(process)
                raise
            if process.returncode not in accepted:
                raise EphorateError(reason, "git_" + args[0])
            return result, process.returncode
    except OSError:
        raise EphorateError(reason, "git_process") from None


def _text(data: bytes, reason: Reason = "unsafe_repository") -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise EphorateError(reason, "git_encoding") from None


def _path(data: bytes) -> str:
    value = _text(data)
    pure = PurePosixPath(value)
    if (
        not value
        or pure.is_absolute()
        or any(part in {"", ".", "..", ".git"} for part in value.split("/"))
        or "\x00" in value
    ):
        raise EphorateError("unsafe_repository", "repository_path")
    return value


def version(deadline: float) -> str:
    output, _ = _run(Path.cwd(), ("--version",), deadline)
    result = _text(output).strip()
    match = re.search(r"git version (\d+)\.(\d+)", result)
    if match is None or (int(match[1]), int(match[2])) < (2, 49):
        raise EphorateError("unsupported_runner", "git_version")
    return result


def repo_root(repo: Path, deadline: float) -> Path:
    path = repo.expanduser().resolve()
    if not path.is_dir():
        raise EphorateError("unsafe_repository", "repository_directory")
    output, _ = _run(path, ("rev-parse", "--show-toplevel"), deadline, reason="unsafe_repository")
    # rev-parse terminates with one newline, which is not necessarily part of the path.
    return Path(_text(output.removesuffix(b"\n"))).resolve()


def _resolve(repo: Path, ref: str, deadline: float) -> str:
    output, _ = _run(
        repo,
        ("rev-parse", "--verify", "--end-of-options", ref + "^{commit}"),
        deadline,
        reason="missing_ref",
    )
    value = _text(output).strip()
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is None:
        raise EphorateError("missing_ref", "resolve")
    return value


def read_tree(repo: Path, revision: str, deadline: float) -> dict[str, TreeEntry]:
    output, _ = _run(
        repo,
        ("ls-tree", "-r", "-z", "--full-tree", revision),
        deadline,
        reason="missing_object",
    )
    result: dict[str, TreeEntry] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, _kind, oid = metadata.split()
        except ValueError:
            raise EphorateError("unsafe_repository", "tree_record") from None
        path = _path(raw_path)
        result[path] = TreeEntry(path, _text(mode), _text(oid))
    return result


def read_blob(repo: Path, oid: str | None, deadline: float) -> bytes:
    if oid is None:
        return b""
    output, _ = _run(repo, ("cat-file", "blob", oid), deadline, reason="missing_object")
    return output


def _configuration(repo: Path, deadline: float) -> dict[str, list[str]]:
    output, _ = _run(repo, ("config", "--null", "--list"), deadline)
    values: dict[str, list[str]] = defaultdict(list)
    for record in output.split(b"\0"):
        if record:
            key, separator, value = record.partition(b"\n")
            values[_text(key).lower()].append(_text(value) if separator else "true")
    return dict(values)


def _active(value: str) -> bool:
    return value.lower() not in {"", "false", "no", "off", "0"}


def _reject_configuration(repo: Path, common_dir: Path, deadline: float) -> None:
    settings = _configuration(repo, deadline)
    for key, values in settings.items():
        if (
            key in {"core.bare", "core.sparsecheckout", "extensions.partialclone"}
            or key.endswith(".promisor")
        ) and any(_active(value) for value in values):
            raise EphorateError("unsafe_repository", "repository_configuration")
        if re.fullmatch(r"filter\..+\.(clean|smudge|process)", key) and any(values):
            raise EphorateError("unsafe_repository", "checkout_filter")
    if (common_dir / "objects/info/alternates").exists():
        raise EphorateError("unsafe_repository", "object_alternates")
    shallow, _ = _run(repo, ("rev-parse", "--is-shallow-repository"), deadline)
    if shallow.strip() != b"false":
        raise EphorateError("unsafe_repository", "shallow_repository")
    flags, _ = _run(repo, ("ls-files", "-v", "-z"), deadline)
    if any(
        record and (record[:1].islower() or record[:1] == b"S") for record in flags.split(b"\0")
    ):
        raise EphorateError("unsafe_repository", "index_flags")


def _validate_tree(
    repo: Path, revision: str | None, entries: dict[str, TreeEntry], deadline: float
) -> None:
    if any(entry.mode not in _REGULAR_MODES for entry in entries.values()):
        raise EphorateError("unsafe_repository", "tree_file_type")
    if not entries:
        return
    raw = b"".join(path.encode("utf-8") + b"\0" for path in entries)
    output, _ = _run(
        repo,
        (
            "check-attr",
            *((f"--source={revision}",) if revision is not None else ()),
            "-z",
            "--stdin",
            "filter",
            "working-tree-encoding",
            "ident",
        ),
        deadline,
        data=raw,
        reason="unsafe_repository",
    )
    records = output.split(b"\0")
    if records[-1:] == [b""]:
        records.pop()
    if len(records) % 3:
        raise EphorateError("unsafe_repository", "attribute_report")
    if any(value not in {b"unspecified", b"unset"} for value in records[2::3]):
        raise EphorateError("unsafe_repository", "checkout_attribute")


def _source_status(
    repo: Path, common_dir: Path, revisions: Sequence[str], deadline: float
) -> bytes:
    """Recheck mutable configuration and attributes before every source status."""
    _reject_configuration(repo, common_dir, deadline)
    entries: dict[str, TreeEntry] = {}
    for revision in revisions:
        tree = read_tree(repo, revision, deadline)
        _validate_tree(repo, revision, tree, deadline)
        entries.update(tree)
    # Uncommitted/info attributes may differ from either immutable Git tree.
    _validate_tree(repo, None, entries, deadline)
    output, _ = _run(
        repo,
        ("status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignore-submodules=none"),
        deadline,
        reason="unsafe_repository",
    )
    return output


def _git_path(repo: Path, name: str, deadline: float) -> Path:
    output, _ = _run(repo, ("rev-parse", "--path-format=absolute", name), deadline)
    return Path(_text(output.removesuffix(b"\n"))).resolve()


def _state(repo: Path, git_dir: Path, deadline: float) -> SourceState:
    head = _resolve(repo, "HEAD", deadline)
    entries = read_tree(repo, head, deadline)
    files: list[tuple[str, str]] = []
    try:
        for path in sorted(entries, key=lambda name: name.encode("utf-8")):
            candidate = repo / path
            if candidate.is_symlink() or not candidate.is_file():
                raise EphorateError("source_changed", "tracked_file")
            files.append((path, hashlib.sha256(candidate.read_bytes()).hexdigest()))
        index_path = git_dir / "index"
        index_hash = hashlib.sha256(index_path.read_bytes()).hexdigest()
    except OSError:
        raise EphorateError("source_changed", "source_snapshot") from None
    output, _ = _run(repo, ("for-each-ref", "--format=%(refname) %(objectname)"), deadline)
    refs = tuple(tuple(line.split(" ", 1)) for line in _text(output).splitlines())
    return SourceState(head, index_hash, tuple((a, b) for a, b in refs), tuple(files))


def _changed_files(repo: Path, base: str, head: str, deadline: float) -> tuple[FileChange, ...]:
    raw, _ = _run(
        repo,
        (
            "diff",
            "--raw",
            "-z",
            "--no-abbrev",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            base,
            head,
            "--",
        ),
        deadline,
    )
    numstat, _ = _run(
        repo,
        (
            "diff",
            "--numstat",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            base,
            head,
            "--",
        ),
        deadline,
    )
    counts: dict[str, tuple[int | None, int | None]] = {}
    for record in numstat.split(b"\0"):
        if record:
            added, deleted, raw_path = record.split(b"\t", 2)
            counts[_path(raw_path)] = (
                None if added == b"-" else int(added),
                None if deleted == b"-" else int(deleted),
            )
    parts = raw.split(b"\0")
    if parts[-1:] == [b""]:
        parts.pop()
    if len(parts) % 2:
        raise EphorateError("unsafe_repository", "diff_record")
    result: list[FileChange] = []
    for index in range(0, len(parts), 2):
        metadata = parts[index].split()
        if len(metadata) != 5 or not metadata[0].startswith(b":"):
            raise EphorateError("unsafe_repository", "diff_record")
        old_mode, new_mode, old_blob, new_blob, status = metadata
        path = _path(parts[index + 1])
        status_text = _text(status)
        if status_text not in {"A", "D", "M", "T"}:
            raise EphorateError("unsafe_repository", "diff_status")
        added_count, deleted_count = counts.get(path, (None, None))
        result.append(
            FileChange(
                path,
                status_text,
                None if set(old_blob) == {ord("0")} else _text(old_blob),
                None if set(new_blob) == {ord("0")} else _text(new_blob),
                None if old_mode == b":000000" else _text(old_mode[1:]),
                None if new_mode == b"000000" else _text(new_mode),
                "other",
                "unsupported_file",
                added_count,
                deleted_count,
            )
        )
    return tuple(sorted(result, key=lambda item: item.path.encode("utf-8")))


def resolve_change(repo: Path, base: str | None, deadline: float) -> Change:
    version(deadline)
    root = repo_root(repo, deadline)
    git_dir = _git_path(root, "--absolute-git-dir", deadline)
    common_dir = _git_path(root, "--git-common-dir", deadline)
    _reject_configuration(root, common_dir, deadline)
    head = _resolve(root, "HEAD", deadline)
    if base is None:
        target, _ = _run(
            root,
            ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"),
            deadline,
            reason="missing_ref",
        )
        default = _resolve(root, _text(target).strip(), deadline)
        bases, _ = _run(
            root, ("merge-base", "--all", head, default), deadline, reason="missing_ref"
        )
        candidates = _text(bases).splitlines()
        if len(candidates) != 1:
            raise EphorateError("missing_ref", "merge_base")
        resolved_base = candidates[0]
    else:
        resolved_base = _resolve(root, base, deadline)
    status_output = _source_status(root, common_dir, (resolved_base, head), deadline)
    if status_output:
        raise EphorateError("unsafe_repository", "dirty_repository")
    base_tree, _ = _run(root, ("rev-parse", resolved_base + "^{tree}"), deadline)
    head_tree, _ = _run(root, ("rev-parse", head + "^{tree}"), deadline)
    source_state = _state(root, git_dir, deadline)
    if source_state.head_sha != head:
        raise EphorateError("source_changed", "source_snapshot")
    return Change(
        root,
        git_dir,
        common_dir,
        resolved_base,
        head,
        _text(base_tree).strip(),
        _text(head_tree).strip(),
        _changed_files(root, resolved_base, head, deadline),
        source_state,
    )


def verify_source_unchanged(change: Change, deadline: float) -> None:
    try:
        state = _state(change.repo, change.git_dir, deadline)
        if state != change.source_state:
            raise EphorateError("source_changed", "source_verification")
        status_output = _source_status(
            change.repo, change.common_dir, (change.base_sha, change.head_sha), deadline
        )
    except EphorateError as error:
        if error.reason == "budget_exhausted":
            raise
        raise EphorateError("source_changed", "source_verification") from None
    if state != change.source_state or status_output:
        raise EphorateError("source_changed", "source_verification")


@contextmanager
def snapshot(change: Change, deadline: float) -> Iterator[Path]:
    parent = _temp_parent((change.repo, change.git_dir, change.common_dir))
    container = Path(tempfile.mkdtemp(prefix="ephorate-snapshot-", dir=parent)).resolve()
    identity = container.stat()
    root = container / "checkout"
    template = container / "template"
    template.mkdir()
    try:
        _run(
            parent,
            (
                "clone",
                "--no-local",
                "--no-checkout",
                "--no-hardlinks",
                "--reject-shallow",
                f"--template={template}",
                "--",
                str(change.repo),
                str(root),
            ),
            deadline,
            ceiling=300,
        )
        for revision in (change.base_sha, change.head_sha):
            _run(
                root, ("cat-file", "-e", revision + "^{commit}"), deadline, reason="missing_object"
            )
        common_dir = _git_path(root, "--git-common-dir", deadline)
        _reject_configuration(root, common_dir, deadline)
        _run(root, ("remote", "remove", "origin"), deadline)
        _run(root, ("checkout", "--detach", change.head_sha), deadline, ceiling=300)
        (container / ".ephorate-owned").write_text(change.head_sha, encoding="ascii")
        yield root
    finally:
        try:
            current = container.lstat()
            if (
                stat.S_ISDIR(current.st_mode)
                and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
                and container.parent == parent
            ):
                shutil.rmtree(container)
            else:
                raise EphorateError("infrastructure_failure", "scratch_ownership")
        except OSError:
            raise EphorateError("infrastructure_failure", "scratch_cleanup") from None


def patch_for_path(change: Change, path: str, deadline: float) -> bytes:
    if path not in {item.path for item in change.files}:
        raise EphorateError("patch_failed", "unknown_changed_path")
    output, _ = _run(
        change.repo,
        ("diff", *_DIFF_OPTIONS, change.base_sha, change.head_sha, "--", path),
        deadline,
    )
    return output


def _file(change: Change, path: str) -> FileChange:
    for item in change.files:
        if item.path == path:
            return item
    raise EphorateError("patch_failed", "unknown_changed_path")


def lines(data: bytes) -> list[bytes]:
    """Split Git text lines on LF only, preserving every original byte."""
    if not data:
        return []
    parts = data.split(b"\n")
    result = [part + b"\n" for part in parts[:-1]]
    if parts[-1]:
        result.append(parts[-1])
    return result


def expected_bytes(
    change: Change, units: Sequence[Unit], deadline: float
) -> dict[str, bytes | None]:
    grouped: dict[str, list[Unit]] = defaultdict(list)
    for unit in units:
        if unit.kind == "file" or unit.classification != "subject":
            raise EphorateError("patch_failed", "unsupported_unit")
        grouped[unit.path].append(unit)
    results: dict[str, bytes | None] = {}
    for path, members in grouped.items():
        item = _file(change, path)
        if item.classification != "subject":
            raise EphorateError("patch_failed", "protected_file")
        base = read_blob(change.repo, item.base_blob, deadline)
        head = read_blob(change.repo, item.head_blob, deadline)
        if any(unit.kind in {"add_file", "delete_file"} for unit in members):
            if len(members) != 1:
                raise EphorateError("patch_failed", "overlapping_units")
            results[path] = None if members[0].kind == "add_file" else base
            continue
        result = lines(head)
        original_head = lines(head)
        base_lines = lines(base)
        previous_start = len(original_head) + 1
        for unit in sorted(members, key=lambda value: value.head_start, reverse=True):
            start = unit.head_start - 1 if unit.head_count else unit.head_start
            base_start = unit.base_start - 1 if unit.base_count else unit.base_start
            if (
                start < 0
                or start + unit.head_count > len(original_head)
                or start + unit.head_count > previous_start
                or base_start < 0
                or base_start + unit.base_count > len(base_lines)
            ):
                raise EphorateError("patch_failed", "hunk_range")
            result[start : start + unit.head_count] = base_lines[
                base_start : base_start + unit.base_count
            ]
            previous_start = start
        results[path] = b"".join(result)
    return results


def _combined_patch(units: Sequence[Unit]) -> bytes:
    grouped: dict[str, list[Unit]] = defaultdict(list)
    for unit in units:
        grouped[unit.path].append(unit)
    patches: list[bytes] = []
    for path in sorted(grouped, key=lambda value: value.encode("utf-8")):
        members = sorted(grouped[path], key=lambda unit: (unit.base_start, unit.head_start))
        if len(members) == 1:
            patches.append(members[0].patch)
            continue
        first = members[0].patch
        match = re.search(rb"^@@ ", first, flags=re.MULTILINE)
        if match is None:
            raise EphorateError("patch_failed", "patch_header")
        patches.append(first[: match.start()])
        for unit in members:
            match = re.search(rb"^@@ ", unit.patch, flags=re.MULTILINE)
            if match is None:
                raise EphorateError("patch_failed", "patch_hunk")
            patches.append(unit.patch[match.start() :])
    return b"".join(patches)


def apply_units(root: Path, change: Change, units: Sequence[Unit], deadline: float) -> None:
    root = root.resolve()
    try:
        owned = (root.parent / ".ephorate-owned").read_text(encoding="ascii")
    except OSError:
        raise EphorateError("patch_failed", "scratch_ownership") from None
    if root.is_relative_to(change.repo) or root.name != "checkout" or owned != change.head_sha:
        raise EphorateError("patch_failed", "scratch_ownership")
    if len({unit.id for unit in units}) != len(units):
        raise EphorateError("patch_failed", "duplicate_unit")
    if not units:
        return
    if _resolve(root, "HEAD", deadline) != change.head_sha:
        raise EphorateError("patch_failed", "scratch_head")
    dirty, _ = _run(root, ("status", "--porcelain=v2", "-z", "--untracked-files=all"), deadline)
    if dirty:
        raise EphorateError("patch_failed", "scratch_dirty")
    expected = expected_bytes(change, units, deadline)
    for path in expected:
        item = _file(change, path)
        candidate = root / path
        if item.head_blob is None:
            if candidate.exists() or candidate.is_symlink():
                raise EphorateError("patch_failed", "head_existence")
        else:
            if candidate.is_symlink() or not candidate.is_file():
                raise EphorateError("patch_failed", "head_file")
            if candidate.read_bytes() != read_blob(change.repo, item.head_blob, deadline):
                raise EphorateError("patch_failed", "head_bytes")
            actual_mode = "100755" if candidate.stat().st_mode & 0o111 else "100644"
            if actual_mode != item.head_mode:
                raise EphorateError("patch_failed", "head_mode")
    patch = _combined_patch(units)
    flags = ("apply", "--reverse", "--index", "--unidiff-zero")
    _run(root, (*flags, "--check"), deadline, data=patch, reason="patch_failed")
    _run(root, flags, deadline, data=patch, reason="patch_failed")
    changed, _ = _run(root, ("diff", "--cached", "--name-only", "-z", "HEAD", "--"), deadline)
    actual_paths = {_path(value) for value in changed.split(b"\0") if value}
    if actual_paths != set(expected):
        raise EphorateError("patch_failed", "changed_paths")
    for path, content in expected.items():
        candidate = root / path
        item = _file(change, path)
        if content is None:
            if candidate.exists() or candidate.is_symlink():
                raise EphorateError("patch_failed", "reversed_existence")
        else:
            if (
                candidate.is_symlink()
                or not candidate.is_file()
                or candidate.read_bytes() != content
            ):
                raise EphorateError("patch_failed", "reversed_bytes")
            mode = item.base_mode if item.status == "D" else item.head_mode
            actual_mode = "100755" if candidate.stat().st_mode & 0o111 else "100644"
            if actual_mode != mode:
                raise EphorateError("patch_failed", "reversed_mode")
