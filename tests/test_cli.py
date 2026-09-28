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

    def test_index_is_deterministic_and_records_normalized_spans(self) -> None:
        self.repository.write("notes/contract.txt", "first\nβeta contract\n")
        revision = self.repository.commit()
        snapshot = self.repository.root / "evidence.jsonl"

        result, output, error = self.invoke(
            "index",
            "--root",
            str(self.repository.root / "notes"),
            "--output",
            str(snapshot),
            "--json",
        )

        self.assertEqual(0, result, error)
        header = json.loads(snapshot.read_text().splitlines()[0])
        self.assertEqual(revision, header["workspace"]["revision"])
        first_snapshot = snapshot.read_bytes()
        records = [json.loads(line) for line in snapshot.read_text().splitlines()]
        span = next(
            record for record in records if record.get("text") == "βeta contract"
        )
        self.assertEqual(
            {
                "start": {"line": 2, "byte_column": 0},
                "end": {"line": 2, "byte_column": 14},
            },
            span["span"],
        )
        self.assertEqual("tower-index", span["collector"]["name"])

        result, _, error = self.invoke(
            "index",
            "--root",
            str(self.repository.root),
            "--output",
            str(snapshot),
        )

        self.assertEqual(0, result, error)
        self.assertEqual(first_snapshot, snapshot.read_bytes())

    def test_search_returns_exact_rg_match_and_resolvable_evidence(self) -> None:
        self.repository.write(
            "docs/contract.txt", "βeta View = compile(Evidence)\nseparate evidence\n"
        )
        self.repository.commit()
        snapshot = self.repository.root / "evidence.jsonl"
        self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )

        result, output, error = self.invoke(
            "search", "View = compile", "--evidence", str(snapshot), "--json"
        )

        self.assertEqual(0, result, error)
        matches = json.loads(output)["results"]
        self.assertEqual(1, len(matches))
        match = matches[0]
        self.assertEqual("docs/contract.txt", match["path"])
        self.assertEqual(
            {
                "start": {"line": 1, "byte_column": 6},
                "end": {"line": 1, "byte_column": 20},
            },
            match["span"],
        )
        self.assertEqual("rg", match["collector"]["name"])
        self.assertFalse(match["stale"])

        result, output, error = self.invoke(
            "evidence", match["id"], "--evidence", str(snapshot), "--json"
        )

        self.assertEqual(0, result, error)
        evidence = json.loads(output)
        self.assertEqual("βeta View = compile(Evidence)", evidence["text"])
        self.assertFalse(evidence["stale"])

    def test_edit_marks_only_that_files_snapshot_evidence_stale(self) -> None:
        self.repository.write("changed.txt", "snapshot needle\n")
        self.repository.write("unchanged.txt", "stable needle\n")
        self.repository.commit()
        snapshot = self.repository.root / "evidence.jsonl"
        self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )
        _, output, _ = self.invoke(
            "search", "needle", "--evidence", str(snapshot), "--json"
        )
        identifiers = {
            result["path"]: result["id"] for result in json.loads(output)["results"]
        }

        self.repository.write("changed.txt", "replacement\n")

        states = {}
        for path, identifier in identifiers.items():
            result, output, error = self.invoke(
                "evidence", identifier, "--evidence", str(snapshot), "--json"
            )
            self.assertEqual(0, result, error)
            states[path] = json.loads(output)["stale"]
        self.assertEqual({"changed.txt": True, "unchanged.txt": False}, states)

        result, output, error = self.invoke(
            "search", "snapshot needle", "--evidence", str(snapshot), "--json"
        )
        self.assertEqual(0, result, error)
        stale_match = json.loads(output)["results"][0]
        self.assertEqual("snapshot needle", stale_match["text"])
        self.assertTrue(stale_match["stale"])


if __name__ == "__main__":
    unittest.main()
