from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Sequence

from tower.arguments import parser
from tower.evidence import (
    EvidenceError,
    build_snapshot,
    load_snapshot,
    resolve_evidence,
    search_snapshot,
    write_snapshot,
)
from tower.representation import (
    RepresentationError,
    collapse_representation,
    compile_representation,
    explain,
    load_representation,
    project_representation,
    refine_representation,
    render_representation,
    trace_representation,
    write_representation,
)
from tower.workspace import (
    Workspace,
    WorkspaceError,
    inspect_workspace,
    searchable_files,
)


SCHEMA_VERSION = 1


class TowerError(Exception):
    """An error that can be shown directly to a CLI user."""


def evidence_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def document(workspace: Workspace, **fields: object) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": asdict(workspace),
        **fields,
    }


def render_status(workspace: Workspace) -> str:
    state = "dirty" if workspace.dirty else "clean"
    return "\n".join(
        (
            f"Workspace: {workspace.root}",
            f"Revision: {workspace.revision}",
            f"Working copy: {state}",
        )
    )


def render_search_result(result: dict[str, object]) -> str:
    span = result["span"]
    start = span["start"]
    end = span["end"]
    state = "stale" if result["stale"] else "fresh"
    location = (
        f"{result['path']}:{start['line']}:{start['byte_column']}-{end['byte_column']}"
    )
    return f"{result['id']}\t{location}\t{state}\t{result['text']}"


def render_evidence(record: dict[str, object]) -> str:
    state = "stale" if record["stale"] else "fresh"
    if record["type"] == "file":
        return f"{record['id']}\t{record['path']}\t{state}\t{record['content_hash']}"
    if record["type"] == "commit":
        return f"{record['id']}\t{str(record['oid'])[:12]}\t{state}\t{record['subject']}"
    if record["type"] == "revision":
        return f"{record['id']}\t{record['oid']}\t{state}"
    if record["type"] == "line-attribution":
        return (
            f"{record['id']}\t{record['path']}:{record['line']}\t{state}\t"
            f"{record['commit_id']}"
        )
    span = record["span"]
    start = span["start"]
    end = span["end"]
    location = (
        f"{record['path']}:{start['line']}:{start['byte_column']}-{end['byte_column']}"
    )
    return f"{record['id']}\t{location}\t{state}\t{record['text']}"


VIEW_QUESTION_FILTER = (
    'select(.schema == "tower-representation-ir" and .schema_version == 1)'
    " | .frame.question"
)


def extract_view_question(path: Path) -> dict[str, object] | None:
    """Extract the question of one saved view through jq."""
    try:
        result = subprocess.run(
            ["jq", "-e", "-c", VIEW_QUESTION_FILTER, str(path)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as error:
        raise TowerError("required command not found: jq") from error

    if result.returncode == 0:
        return json.loads(result.stdout)
    if result.returncode in (1, 4, 5):
        return None
    detail = result.stderr.strip() or f"exit status {result.returncode}"
    raise TowerError(f"jq failed: {detail}")


def collect_view_questions(directory: Path) -> tuple[list[dict[str, object]], int]:
    """Load the question of every saved view under directory, in path order."""
    if not directory.is_dir():
        raise TowerError(f"directory not found: {directory}")
    questions: list[dict[str, object]] = []
    skipped = 0
    for path in sorted(directory.rglob("*.json")):
        if not path.is_file():
            continue
        question = extract_view_question(path)
        if question is None:
            skipped += 1
        else:
            questions.append(question)
    return questions, skipped


def run_workspace_command(arguments: argparse.Namespace) -> None:
    workspace = inspect_workspace(arguments.root)
    files = searchable_files(workspace) if arguments.command == "files" else None
    if arguments.format == "json":
        fields = {"files": files} if files is not None else {}
        payload = document(workspace, **fields)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    elif files is not None:
        print("\n".join(files))
    else:
        print(render_status(workspace))


def run_index(arguments: argparse.Namespace) -> None:
    workspace = inspect_workspace(arguments.root)
    output = Path(arguments.output).expanduser()
    if not output.is_absolute():
        output = Path(workspace.root) / output
    output = output.resolve()
    records = build_snapshot(Path(workspace.root), workspace.revision, output)
    write_snapshot(records, output)
    file_count = sum(record["type"] == "file" for record in records)
    span_count = sum(record["type"] == "span" for record in records)
    if arguments.format == "json":
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "output": str(output),
                    "files": file_count,
                    "spans": span_count,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(f"Indexed {file_count} files and {span_count} spans: {output}")


def run_views(arguments: argparse.Namespace) -> None:
    workspace = inspect_workspace(arguments.root)
    directory = Path(workspace.root) / ".tower"
    if not directory.is_dir():
        raise TowerError(
            f"no tower build found: {directory} does not exist; run 'tower index' first"
        )
    questions, skipped = collect_view_questions(directory)
    if arguments.format == "json":
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "dir": str(directory),
                    "questions": questions,
                    "skipped": skipped,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return
    if questions:
        print("\n".join(str(item["text"]) for item in questions))
    else:
        print(f"No saved views found in {directory}")
    if skipped:
        print(f"Skipped {skipped} file(s) that are not saved views.")


def run_explain(arguments: argparse.Namespace) -> None:
    view = load_representation(evidence_path(arguments.view))
    print(explain(view, arguments.id))


def run_transformation(arguments: argparse.Namespace) -> None:
    view = load_representation(evidence_path(arguments.view))
    if arguments.command == "refine":
        transformed = refine_representation(
            view,
            arguments.id,
            detail=arguments.detail,
            budget_units=arguments.budget_units,
        )
    elif arguments.command == "trace":
        transformed = trace_representation(view, arguments.id)
    elif arguments.command == "project":
        transformed = project_representation(view, arguments.relationship_type)
    else:
        transformed = collapse_representation(view, arguments.region_id)
    output = evidence_path(arguments.output)
    write_representation(transformed, output)
    print(str(output))


def run_map(arguments: argparse.Namespace) -> None:
    if arguments.view:
        print(render_representation(load_representation(evidence_path(arguments.view))))
        return
    run_compilation(arguments)


def run_compilation(arguments: argparse.Namespace) -> None:
    required = (
        "evidence",
        "question",
        "intent",
        "terms",
        "focus",
        "viewpoint",
        "detail",
        "budget_units",
    )
    missing = [name for name in required if getattr(arguments, name) is None]
    if missing:
        raise TowerError(
            "map requires --view or a complete compilation request; missing "
            + ", ".join("--" + name.replace("_", "-") for name in missing)
        )
    records = load_snapshot(evidence_path(arguments.evidence))
    view = compile_representation(
        records,
        question=arguments.question,
        intent=arguments.intent,
        terms=arguments.terms,
        focus=arguments.focus,
        viewpoint=arguments.viewpoint,
        detail=arguments.detail,
        budget_units=arguments.budget_units,
    )
    if arguments.output:
        write_representation(view, evidence_path(arguments.output))
    if arguments.command == "compile":
        print(str(evidence_path(arguments.output)))
    else:
        print(render_representation(view))


def run_evidence_command(arguments: argparse.Namespace) -> None:
    snapshot = evidence_path(arguments.evidence)
    records = load_snapshot(snapshot)
    if arguments.command == "search":
        results = search_snapshot(records, arguments.query)
        if arguments.format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "evidence": str(snapshot),
                        "query": arguments.query,
                        "results": results,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print("\n".join(render_search_result(result) for result in results))
        return

    record = resolve_evidence(records, arguments.id)
    if arguments.format == "json":
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    else:
        print(render_evidence(record))


COMMANDS: dict[str, Callable[[argparse.Namespace], None]] = {
    "status": run_workspace_command,
    "files": run_workspace_command,
    "index": run_index,
    "views": run_views,
    "search": run_evidence_command,
    "evidence": run_evidence_command,
    "compile": run_compilation,
    "map": run_map,
    "explain": run_explain,
    "refine": run_transformation,
    "trace": run_transformation,
    "project": run_transformation,
    "collapse": run_transformation,
}


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        COMMANDS[arguments.command](arguments)
        return 0
    except (EvidenceError, RepresentationError, TowerError, WorkspaceError, OSError) as error:
        print(f"tower: {error}", file=sys.stderr)
        return 1
