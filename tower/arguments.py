from __future__ import annotations

import argparse

from tower.representation import SUPPORTED_DETAILS, SUPPORTED_VIEWPOINTS


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

    session_start = subparsers.add_parser("session-start")
    session_start.add_argument("--task", required=True, help="public evaluation task JSON")
    session_start.add_argument("--condition", choices=("baseline", "tower"), required=True)
    session_start.add_argument("--root", default=".", help="pinned Git workspace")
    session_start.add_argument("--output", required=True, help="evaluation session JSON")

    session_record = subparsers.add_parser("session-record")
    session_record.add_argument(
        "action", choices=("query", "navigation", "transformation", "evidence-opened")
    )
    session_record.add_argument("value", help="command, stable ID, span, or navigation target")
    session_record.add_argument("--session", required=True, help="evaluation session JSON")

    session_submit = subparsers.add_parser("session-submit")
    session_submit.add_argument("--session", required=True, help="evaluation session JSON")
    session_submit.add_argument("--answer", required=True, help="plain-text answer path")
    session_submit.add_argument("--confidence", type=int, help="confidence from 0 to 100")

    score = subparsers.add_parser("score")
    score.add_argument("--session", required=True, help="submitted evaluation session JSON")
    score.add_argument("--rubric", required=True, help="private ground-truth rubric JSON")
    score.add_argument("--assessment", required=True, help="explicit assessor judgment JSON")
    score.add_argument("--output", required=True, help="evaluation score JSON")

    compare = subparsers.add_parser("compare")
    compare.add_argument("--baseline", required=True, help="baseline score JSON")
    compare.add_argument("--tower", required=True, help="Tower-assisted score JSON")
    compare.add_argument("--output", required=True, help="comparison JSON")
    return cli
