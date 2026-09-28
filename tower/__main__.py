from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


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
    return cli


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        workspace = inspect_workspace(arguments.root)
        files = searchable_files(workspace) if arguments.command == "files" else None
    except TowerError as error:
        print(f"tower: {error}", file=sys.stderr)
        return 1

    if arguments.format == "json":
        payload = document(workspace, **({"files": files} if files is not None else {}))
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    elif files is not None:
        print("\n".join(files))
    else:
        print(render_status(workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
