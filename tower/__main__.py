from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from tower.evidence import (
    EvidenceError,
    build_snapshot,
    load_snapshot,
    resolve_evidence,
    search_snapshot,
    write_snapshot,
)
from tower.representation import (
    SUPPORTED_DETAILS,
    SUPPORTED_VIEWPOINTS,
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


SCHEMA_VERSION = 1


class TowerError(Exception):
    """An error that can be shown directly to a CLI user."""


@dataclass(frozen=True)
class Workspace:
    root: str
    revision: str
    dirty: bool
    vcs: str = "git"


def run(command: Sequence[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as error:
        raise TowerError(f"required command not found: {command[0]}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise TowerError(f"{command[0]} failed: {detail}")
    return result.stdout


def inspect_workspace(root: str) -> Workspace:
    requested_root = Path(root).expanduser().resolve()
    if not requested_root.is_dir():
        raise TowerError(f"root is not a directory: {requested_root}")

    workspace_root = Path(
        run(["git", "rev-parse", "--show-toplevel"], cwd=requested_root).strip()
    ).resolve()
    revision = run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=workspace_root
    ).strip()
    dirty = bool(
        run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=workspace_root,
        ).strip()
    )
    return Workspace(root=str(workspace_root), revision=revision, dirty=dirty)


def searchable_files(workspace: Workspace) -> list[str]:
    root = Path(workspace.root)
    try:
        result = subprocess.run(
            ["rg", "--files"],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as error:
        raise TowerError("required command not found: rg") from error

    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise TowerError(f"rg failed: {detail}")
    return sorted(path for path in result.stdout.splitlines() if path)


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
        # Valid JSON without a view frame (1, 4) or unreadable as JSON (5).
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
            continue
        questions.append(question)
    return questions, skipped


def add_format_arguments(command: argparse.ArgumentParser, *, default: str) -> None:
    command.add_argument(
        "--format",
        choices=("compact", "json"),
        default=default,
        help=f"output format (default: {default})",
    )
    command.add_argument(
        "--json",
        action="store_const",
        const="json",
        dest="format",
        help="shorthand for --format json",
    )


def add_compiler_arguments(
    command: argparse.ArgumentParser, *, required: bool
) -> None:
    command.add_argument("--evidence", required=required, help="JSON Lines snapshot path")
    command.add_argument("--question", required=required, help="information need")
    command.add_argument("--intent", required=required, help="explicit question intent")
    command.add_argument(
        "--term",
        action="append",
        dest="terms",
        required=required,
        help="exact relevance term; repeat for multiple terms",
    )
    command.add_argument("--focus", required=required, help="evidence path or stable ID")
    command.add_argument(
        "--viewpoint",
        required=required,
        help="representation viewpoint (supported: " + ", ".join(SUPPORTED_VIEWPOINTS) + ")",
    )
    command.add_argument("--detail", choices=SUPPORTED_DETAILS, required=required)
    command.add_argument("--budget-units", type=int, required=required)


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="tower")
    subparsers = cli.add_subparsers(dest="command", required=True)

    for name in ("status", "files"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", default=".", help="path inside a Git workspace")
        command.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="output format (default: text)",
        )
        command.add_argument(
            "--json",
            action="store_const",
            const="json",
            dest="format",
            help="shorthand for --format json",
        )

    index = subparsers.add_parser("index")
    index.add_argument("--root", default=".", help="path inside a Git workspace")
    index.add_argument("--output", required=True, help="JSON Lines snapshot path")
    add_format_arguments(index, default="compact")

    views = subparsers.add_parser(
        "views",
        help="list the questions recorded in saved Representation IR files under .tower",
    )
    views.add_argument("--root", default=".", help="path inside a Git workspace")
    add_format_arguments(views, default="text")

    search = subparsers.add_parser("search")
    search.add_argument("query", help="regular expression passed to rg")
    search.add_argument("--evidence", required=True, help="JSON Lines snapshot path")
    add_format_arguments(search, default="compact")

    evidence = subparsers.add_parser("evidence")
    evidence.add_argument("id", help="file or source-span evidence ID")
    evidence.add_argument("--evidence", required=True, help="JSON Lines snapshot path")
    add_format_arguments(evidence, default="compact")

    compile_command = subparsers.add_parser("compile")
    add_compiler_arguments(compile_command, required=True)
    compile_command.add_argument("--output", required=True, help="Representation IR path")

    map_command = subparsers.add_parser("map")
    map_command.add_argument(
        "--view", help="render saved Representation IR instead of compiling"
    )
    map_command.add_argument("--output", help="also save compiled Representation IR")
    add_compiler_arguments(map_command, required=False)

    explain_command = subparsers.add_parser("explain")
    explain_command.add_argument("id", help="visible or omitted unit ID")
    explain_command.add_argument("--view", required=True, help="Representation IR path")

    refine = subparsers.add_parser("refine")
    refine.add_argument("id", help="visible boundary unit ID")
    refine.add_argument("--view", required=True, help="Representation IR path")
    refine.add_argument("--detail", choices=SUPPORTED_DETAILS, default="evidence")
    refine.add_argument("--budget-units", type=int, default=5)
    refine.add_argument("--output", required=True, help="transformed Representation IR path")

    trace = subparsers.add_parser("trace")
    trace.add_argument("id", help="visible unit ID")
    trace.add_argument("--view", required=True, help="Representation IR path")
    trace.add_argument("--output", required=True, help="transformed Representation IR path")

    project = subparsers.add_parser("project")
    project.add_argument("relationship_type", help="relationship type to retain")
    project.add_argument("--view", required=True, help="Representation IR path")
    project.add_argument("--output", required=True, help="transformed Representation IR path")

    collapse = subparsers.add_parser("collapse")
    collapse.add_argument("region_id", help="refined region ID")
    collapse.add_argument("--view", required=True, help="Representation IR path")
    collapse.add_argument("--output", required=True, help="transformed Representation IR path")
    return cli


def evidence_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


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


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command in ("status", "files"):
            workspace = inspect_workspace(arguments.root)
            files = searchable_files(workspace) if arguments.command == "files" else None
            if arguments.format == "json":
                payload = document(
                    workspace, **({"files": files} if files is not None else {})
                )
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            elif files is not None:
                print("\n".join(files))
            else:
                print(render_status(workspace))
            return 0

        if arguments.command == "index":
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
            return 0

        if arguments.command == "views":
            workspace = inspect_workspace(arguments.root)
            directory = Path(workspace.root) / ".tower"
            if not directory.is_dir():
                raise TowerError(
                    f"no tower build found: {directory} does not exist; "
                    "run 'tower index' first"
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
                return 0
            if questions:
                print("\n".join(str(item["text"]) for item in questions))
            else:
                print(f"No saved views found in {directory}")
            if skipped:
                print(f"Skipped {skipped} file(s) that are not saved views.")
            return 0

        if arguments.command == "explain":
            view = load_representation(evidence_path(arguments.view))
            print(explain(view, arguments.id))
            return 0

        if arguments.command in ("refine", "trace", "project", "collapse"):
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
            return 0

        if arguments.command == "map" and arguments.view:
            print(render_representation(load_representation(evidence_path(arguments.view))))
            return 0

        if arguments.command in ("compile", "map"):
            missing = [
                name
                for name in (
                    "evidence",
                    "question",
                    "intent",
                    "terms",
                    "focus",
                    "viewpoint",
                    "detail",
                    "budget_units",
                )
                if getattr(arguments, name) is None
            ]
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
            return 0

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
            return 0

        record = resolve_evidence(records, arguments.id)
        if arguments.format == "json":
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
        else:
            print(render_evidence(record))
        return 0
    except (EvidenceError, RepresentationError, TowerError, OSError) as error:
        print(f"tower: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
