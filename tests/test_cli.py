from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tower.__main__ import main


class Repository:
    def __init__(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="tower workspace ünicode "
        )
        self.root = Path(self.temporary_directory.name).resolve()
        self.git("init", "--quiet")
        self.git("config", "user.email", "tower@example.test")
        self.git("config", "user.name", "Tower Tests")

    def close(self) -> None:
        self.temporary_directory.cleanup()

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def write(self, path: str, content: str = "content\n") -> None:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def commit(self) -> str:
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "fixture")
        return self.git("rev-parse", "HEAD")


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Repository()
        self.addCleanup(self.repository.close)

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_status_identifies_workspace_and_revision_from_nested_path(self) -> None:
        self.repository.write("nested directory/placeholder.txt")
        revision = self.repository.commit()

        result, output, error = self.invoke(
            "status", "--root", str(self.repository.root / "nested directory"), "--json"
        )

        self.assertEqual(0, result, error)
        payload = json.loads(output)
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual(str(self.repository.root), payload["workspace"]["root"])
        self.assertEqual(revision, payload["workspace"]["revision"])
        self.assertEqual("git", payload["workspace"]["vcs"])
        self.assertFalse(payload["workspace"]["dirty"])

    def test_status_reports_dirty_working_copy(self) -> None:
        self.repository.write("tracked.txt")
        self.repository.commit()
        self.repository.write("tracked.txt", "changed\n")

        result, output, error = self.invoke(
            "status", "--root", str(self.repository.root), "--format", "json"
        )

        self.assertEqual(0, result, error)
        self.assertTrue(json.loads(output)["workspace"]["dirty"])

    def test_files_honor_ignores_and_preserve_unicode_paths(self) -> None:
        visible_path = "source files/naïve module.py"
        self.repository.write(visible_path)
        self.repository.write("ignored/generated.txt")
        self.repository.write(".gitignore", "ignored/\n")
        revision = self.repository.commit()

        result, output, error = self.invoke(
            "files", "--root", str(self.repository.root / "source files"), "--json"
        )

        self.assertEqual(0, result, error)
        payload = json.loads(output)
        self.assertEqual(revision, payload["workspace"]["revision"])
        self.assertIn(visible_path, payload["files"])
        self.assertNotIn("ignored/generated.txt", payload["files"])
        self.assertEqual(sorted(payload["files"]), payload["files"])

    def test_text_output_is_for_people(self) -> None:
        self.repository.write("tracked.txt")
        revision = self.repository.commit()

        result, output, error = self.invoke(
            "status", "--root", str(self.repository.root)
        )

        self.assertEqual(0, result, error)
        self.assertIn(f"Workspace: {self.repository.root}", output)
        self.assertIn(f"Revision: {revision}", output)
        self.assertIn("Working copy: clean", output)


if __name__ == "__main__":
    unittest.main()
