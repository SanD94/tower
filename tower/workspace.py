from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class WorkspaceError(Exception):
    """An error encountered while inspecting a workspace."""


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
        raise WorkspaceError(f"required command not found: {command[0]}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise WorkspaceError(f"{command[0]} failed: {detail}")
    return result.stdout


def inspect_workspace(root: str) -> Workspace:
    requested_root = Path(root).expanduser().resolve()
    if not requested_root.is_dir():
        raise WorkspaceError(f"root is not a directory: {requested_root}")

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
        raise WorkspaceError("required command not found: rg") from error

    if result.returncode not in (0, 1):
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise WorkspaceError(f"rg failed: {detail}")
    return sorted(path for path in result.stdout.splitlines() if path)
