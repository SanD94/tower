from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence


SNAPSHOT_SCHEMA_VERSION = 2


class EvidenceError(Exception):
    """An error that can be shown directly to a CLI user."""


def run_rg(arguments: Sequence[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["rg", *arguments],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except FileNotFoundError as error:
        raise EvidenceError("required command not found: rg") from error

    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise EvidenceError(f"rg failed: {detail}")
    return result.stdout


def run_git(
    arguments: Sequence[str], *, cwd: Path, allowed_statuses: tuple[int, ...] = (0,)
) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except FileNotFoundError as error:
        raise EvidenceError("required command not found: git") from error
    if result.returncode not in allowed_statuses:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise EvidenceError(f"git failed: {detail}")
    return result.stdout if result.returncode == 0 else None


def evidence_id(kind: str, *parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()
    return f"{kind}-{hashlib.sha256(encoded).hexdigest()[:20]}"


def discover_files(root: Path, excluded: Path) -> list[str]:
    output = run_git(
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
        cwd=root,
    ) or ""
    paths = output.split("\0")
    discovered = []
    for path in paths:
        if not path:
            continue
        source = root / path
        if source.resolve() != excluded and (source.is_file() or source.is_symlink()):
            discovered.append(path)
    return sorted(discovered)


def git_blob_oid(root: Path, content: bytes) -> str:
    try:
        result = subprocess.run(
            ["git", "hash-object", "--stdin"],
            cwd=root,
            input=content,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise EvidenceError("required command not found: git") from error
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise EvidenceError(f"git failed: {detail or f'exit status {result.returncode}'}")
    return result.stdout.decode("ascii").strip()


def indexed_lines(content: bytes) -> Iterable[tuple[int, bytes, bytes]]:
    for number, line in enumerate(content.splitlines(keepends=True), start=1):
        text = line.rstrip(b"\r\n")
        yield number, text, line[len(text) :]


def collect_git_evidence(
    root: Path,
    revision: str,
    files: Sequence[dict[str, object]],
    spans: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = [
        {
            "type": "revision",
            "id": evidence_id("revision", revision),
            "oid": revision,
            "collector": {
                "name": "git",
                "command": ["git", "rev-parse", "--verify", "HEAD"],
            },
        }
    ]
    history = run_git(["rev-list", "--topo-order", revision], cwd=root) or ""
    for oid in history.splitlines():
        metadata = run_git(
            ["show", "-s", "--format=%H%x00%P%x00%an%x00%ae%x00%aI%x00%s", oid],
            cwd=root,
        )
        if metadata is None:
            continue
        fields = metadata.rstrip("\n").split("\0")
        changed_output = run_git(
            ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", oid],
            cwd=root,
        ) or ""
        changed_files = sorted(path for path in changed_output.split("\0") if path)
        diff = run_git(
            ["show", "--format=", "--no-ext-diff", "--unified=3", oid, "--"],
            cwd=root,
        )
        records.append(
            {
                "type": "commit",
                "id": evidence_id("commit", oid),
                "oid": fields[0],
                "parents": fields[1].split() if fields[1] else [],
                "author": {"name": fields[2], "email": fields[3]},
                "authored_at": fields[4],
                "subject": fields[5],
                "changed_files": changed_files,
                "diff": diff or "",
                "collector": {
                    "name": "git",
                    "commands": [
                        [
                            "git",
                            "show",
                            "-s",
                            "--format=%H%x00%P%x00%an%x00%ae%x00%aI%x00%s",
                            oid,
                        ],
                        [
                            "git",
                            "diff-tree",
                            "--root",
                            "--no-commit-id",
                            "--name-only",
                            "-r",
                            "-z",
                            oid,
                        ],
                        [
                            "git",
                            "show",
                            "--format=",
                            "--no-ext-diff",
                            "--unified=3",
                            oid,
                            "--",
                        ],
                    ],
                },
            }
        )

    spans_by_path_and_line = {
        (str(span["path"]), int(span["span"]["start"]["line"])): span
        for span in spans
    }
    for file_record in files:
        if file_record.get("encoding") != "utf-8":
            continue
        path = str(file_record["path"])
        blame = run_git(
            ["blame", "--line-porcelain", "--", path],
            cwd=root,
            allowed_statuses=(0, 128),
        )
        if blame is None:
            continue
        for line in blame.splitlines():
            parts = line.split()
            if not parts:
                continue
            oid = parts[0].lstrip("^")
            if len(parts) < 4 or len(oid) != len(revision) or set(oid) == {"0"}:
                continue
            try:
                final_line = int(parts[2])
            except ValueError:
                continue
            span = spans_by_path_and_line.get((path, final_line))
            if span is None:
                continue
            records.append(
                {
                    "type": "line-attribution",
                    "id": evidence_id("attribution", span["id"], oid),
                    "span_id": span["id"],
                    "file_id": file_record["id"],
                    "path": path,
                    "line": final_line,
                    "commit_id": evidence_id("commit", oid),
                    "collector": {
                        "name": "git",
                        "command": [
                            "git",
                            "blame",
                            "--line-porcelain",
                            "--",
                            path,
                        ],
                    },
                }
            )
    return records


def build_snapshot(root: Path, revision: str, output: Path) -> list[dict[str, object]]:
    status_arguments = ["status", "--porcelain", "--untracked-files=normal", "--", "."]
    try:
        output_path = output.relative_to(root).as_posix()
    except ValueError:
        pass
    else:
        status_arguments.append(f":(exclude,top){output_path}")
    dirty = bool((run_git(status_arguments, cwd=root) or "").strip())
    records: list[dict[str, object]] = []
    file_records: list[dict[str, object]] = []
    span_records: list[dict[str, object]] = []
    for path in discover_files(root, output):
        content = (root / path).read_bytes()
        blob_oid = git_blob_oid(root, content)
        file_id = evidence_id("file", path, blob_oid)
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            encoding = "binary"
        else:
            encoding = "utf-8"
        file_record = {
            "type": "file",
            "id": file_id,
            "path": path,
            "blob_oid": blob_oid,
            "size_bytes": len(content),
            "encoding": encoding,
            "collector": {
                "name": "git",
                "commands": [
                    [
                        "git",
                        "ls-files",
                        "--cached",
                        "--others",
                        "--exclude-standard",
                        "-z",
                        "--",
                        ".",
                    ],
                    ["git", "hash-object", "--stdin"],
                ],
            },
        }
        records.append(file_record)
        file_records.append(file_record)
        if encoding != "utf-8":
            continue
        for line_number, text_bytes, ending in indexed_lines(content):
            text = text_bytes.decode("utf-8")
            span_record = {
                "type": "span",
                "id": evidence_id("span", path, line_number, text),
                "file_id": file_id,
                "path": path,
                "span": {
                    "start": {"line": line_number, "byte_column": 0},
                    "end": {"line": line_number, "byte_column": len(text_bytes)},
                },
                "text": text,
                "line_ending": ending.decode("ascii"),
                "collector": {"name": "tower-index", "method": "utf-8-line-span"},
            }
            records.append(span_record)
            span_records.append(span_record)
    worktree = [
        {"path": record["path"], "blob_oid": record["blob_oid"]}
        for record in file_records
    ]
    records.insert(
        0,
        {
            "type": "snapshot",
            "id": evidence_id("snapshot", str(root), revision, worktree),
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "workspace": {
                "root": str(root),
                "revision": revision,
                "dirty": dirty,
                "vcs": "git",
            },
            "worktree": {"files": worktree},
            "collector": {
                "name": "tower-index",
                "file_discovery": [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "-z",
                    "--",
                    ".",
                ],
            },
        },
    )
    records.extend(collect_git_evidence(root, revision, file_records, span_records))
    return records


def write_snapshot(records: Sequence[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _read_snapshot(path: Path) -> list[dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise EvidenceError(f"cannot read evidence snapshot {path}: {error}") from error
    try:
        records = [json.loads(line) for line in lines]
    except json.JSONDecodeError as error:
        raise EvidenceError(f"invalid evidence snapshot {path}: {error}") from error
    if not records or records[0].get("type") != "snapshot":
        raise EvidenceError(f"invalid evidence snapshot {path}: missing snapshot record")
    return records


def load_snapshot(path: Path) -> list[dict[str, object]]:
    records = _read_snapshot(path)
    if records[0].get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise EvidenceError(
            f"unsupported evidence schema: {records[0].get('schema_version')}"
        )
    return records


def snapshot_root(records: Sequence[dict[str, object]]) -> Path:
    workspace = records[0].get("workspace")
    if not isinstance(workspace, dict) or not isinstance(workspace.get("root"), str):
        raise EvidenceError("invalid evidence snapshot: missing workspace root")
    return Path(workspace["root"])


def stale_worktree_paths(root: Path, files: object) -> list[str]:
    if not isinstance(files, list):
        return []
    stale: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        blob_oid = item.get("blob_oid")
        if not isinstance(path, str) or not isinstance(blob_oid, str):
            continue
        try:
            current_oid = git_blob_oid(root, (root / path).read_bytes())
        except OSError:
            current_oid = None
        if current_oid != blob_oid:
            stale.append(path)
    return stale


def stale_file_ids(records: Sequence[dict[str, object]]) -> set[str]:
    root = snapshot_root(records)
    stale_paths = set(
        stale_worktree_paths(root, records[0].get("worktree", {}).get("files", []))
    )
    return {
        str(record["id"])
        for record in records
        if record.get("type") == "file" and record.get("path") in stale_paths
    }


def snapshot_is_stale(records: Sequence[dict[str, object]]) -> bool:
    root = snapshot_root(records)
    workspace = records[0].get("workspace", {})
    recorded_revision = workspace.get("revision") if isinstance(workspace, dict) else None
    current_revision = (run_git(["rev-parse", "--verify", "HEAD"], cwd=root) or "").strip()
    return current_revision != recorded_revision or bool(stale_file_ids(records))


def frame_is_stale(frame: object) -> bool | None:
    if not isinstance(frame, dict):
        return None
    workspace = frame.get("workspace")
    worktree = frame.get("worktree")
    if not isinstance(workspace, dict) or not isinstance(worktree, dict):
        return None
    root_value = workspace.get("root")
    revision = workspace.get("revision")
    if not isinstance(root_value, str) or not isinstance(revision, str):
        return None
    root = Path(root_value)
    if not root.is_dir():
        return None
    current_revision = (run_git(["rev-parse", "--verify", "HEAD"], cwd=root) or "").strip()
    return current_revision != revision or bool(
        stale_worktree_paths(root, worktree.get("files"))
    )


def reconstruct_snapshot(records: Sequence[dict[str, object]], destination: Path) -> None:
    spans_by_file: dict[str, list[dict[str, object]]] = {}
    for record in records:
        if record.get("type") == "span":
            spans_by_file.setdefault(str(record["file_id"]), []).append(record)
    for record in records:
        if record.get("type") != "file" or record.get("encoding") != "utf-8":
            continue
        target = destination / str(record["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        spans = spans_by_file.get(str(record["id"]), [])
        content = "".join(
            str(span["text"]) + str(span["line_ending"])
            for span in sorted(spans, key=lambda item: item["span"]["start"]["line"])
        )
        target.write_text(content, encoding="utf-8", newline="")


def search_snapshot(
    records: Sequence[dict[str, object]], query: str
) -> list[dict[str, object]]:
    spans = {
        (str(record["path"]), int(record["span"]["start"]["line"])): record
        for record in records
        if record.get("type") == "span"
    }
    stale = stale_file_ids(records)
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tower evidence search ") as directory:
        search_root = Path(directory)
        reconstruct_snapshot(records, search_root)
        output = run_rg(["--json", "--", query, "."], cwd=search_root)
        for line in output.splitlines():
            event = json.loads(line)
            if event.get("type") != "match":
                continue
            data = event["data"]
            path = str(data["path"]["text"])
            if path.startswith("./"):
                path = path[2:]
            line_number = int(data["line_number"])
            span_record = spans[(path, line_number)]
            for match in data["submatches"]:
                results.append(
                    {
                        "id": span_record["id"],
                        "path": path,
                        "span": {
                            "start": {
                                "line": line_number,
                                "byte_column": int(match["start"]),
                            },
                            "end": {
                                "line": line_number,
                                "byte_column": int(match["end"]),
                            },
                        },
                        "text": span_record["text"],
                        "stale": span_record["file_id"] in stale,
                        "collector": {
                            "name": "rg",
                            "command": ["rg", "--json", "--", query, "."],
                            "query": query,
                        },
                    }
                )
    return results


def resolve_evidence(
    records: Sequence[dict[str, object]], identifier: str
) -> dict[str, object]:
    record = next((item for item in records if item.get("id") == identifier), None)
    if record is None:
        raise EvidenceError(f"evidence not found: {identifier}")
    result = dict(record)
    stale = stale_file_ids(records)
    file_id = identifier if record.get("type") == "file" else record.get("file_id")
    result["stale"] = file_id in stale
    return result
