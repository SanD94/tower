from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Sequence


SNAPSHOT_SCHEMA_VERSION = 1


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
        )
    except FileNotFoundError as error:
        raise EvidenceError("required command not found: rg") from error

    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise EvidenceError(f"rg failed: {detail}")
    return result.stdout


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def evidence_id(kind: str, *parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()
    return f"{kind}-{hashlib.sha256(encoded).hexdigest()[:20]}"


def discover_files(root: Path, excluded: Path) -> list[str]:
    paths = run_rg(["--files", "--null"], cwd=root).split("\0")
    discovered = []
    for path in paths:
        if not path:
            continue
        if (root / path).resolve() != excluded:
            discovered.append(path)
    return sorted(discovered)


def indexed_lines(content: bytes) -> Iterable[tuple[int, bytes, bytes]]:
    for number, line in enumerate(content.splitlines(keepends=True), start=1):
        text = line.rstrip(b"\r\n")
        yield number, text, line[len(text) :]


def build_snapshot(root: Path, revision: str, output: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = [
        {
            "type": "snapshot",
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "workspace": {"root": str(root), "revision": revision, "vcs": "git"},
            "collector": {
                "name": "tower-index",
                "file_discovery": ["rg", "--files", "--null"],
            },
        }
    ]
    for path in discover_files(root, output):
        content = (root / path).read_bytes()
        digest = content_hash(content)
        file_id = evidence_id("file", path, digest)
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            encoding = "binary"
        else:
            encoding = "utf-8"
        records.append(
            {
                "type": "file",
                "id": file_id,
                "path": path,
                "content_hash": digest,
                "size_bytes": len(content),
                "encoding": encoding,
                "collector": {"name": "rg", "command": ["rg", "--files", "--null"]},
            }
        )
        if encoding != "utf-8":
            continue
        for line_number, text_bytes, ending in indexed_lines(content):
            text = text_bytes.decode("utf-8")
            records.append(
                {
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
            )
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


def load_snapshot(path: Path) -> list[dict[str, object]]:
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


def stale_file_ids(records: Sequence[dict[str, object]]) -> set[str]:
    root = snapshot_root(records)
    stale: set[str] = set()
    for record in records:
        if record.get("type") != "file":
            continue
        source = root / str(record["path"])
        try:
            current_hash = content_hash(source.read_bytes())
        except OSError:
            current_hash = None
        if current_hash != record["content_hash"]:
            stale.add(str(record["id"]))
    return stale


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
