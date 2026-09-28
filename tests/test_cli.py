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

    def commit(self, message: str = "fixture") -> str:
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", message)
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

    def representation_fixture(self) -> Path:
        self.repository.write(
            "docs/design.md",
            "# Tower\n"
            "## Compiler\n"
            "The compiler creates representations.\n"
            "## Client\n"
            "The client renders compiler output.\n",
        )
        self.repository.write("docs/other.md", "# Other\nclient boundary\n")
        self.repository.commit()
        snapshot = self.repository.root / "evidence.jsonl"
        result, _, error = self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )
        self.assertEqual(0, result, error)
        return snapshot

    def compile_arguments(
        self, snapshot: Path, *terms: str, budget: int = 20
    ) -> tuple[str, ...]:
        arguments = [
            "--evidence",
            str(snapshot),
            "--question",
            "Where are compiler and client responsibilities?",
            "--intent",
            "locate-evidence",
        ]
        for term in terms or ("compiler", "client"):
            arguments.extend(("--term", term))
        arguments.extend(
            (
                "--focus",
                "docs/design.md",
                "--viewpoint",
                "topology",
                "--detail",
                "summary",
                "--budget-units",
                str(budget),
            )
        )
        return tuple(arguments)

    def test_compile_writes_bounded_provenance_backed_representation(self) -> None:
        snapshot = self.representation_fixture()
        view_path = self.repository.root / "view.json"

        result, output, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, budget=6),
            "--output",
            str(view_path),
        )

        self.assertEqual(0, result, error)
        self.assertEqual(str(view_path), output.strip())
        view = json.loads(view_path.read_text())
        self.assertEqual("tower-representation-ir", view["schema"])
        self.assertEqual(1, view["schema_version"])
        self.assertEqual(6, len(view["units"]))
        self.assertTrue(view["omissions"])
        self.assertEqual(
            {"compiler", "client"},
            {
                unit["provenance"]["matched_by"]
                for unit in view["units"]
                if unit["type"] == "match"
            },
        )
        self.assertEqual(
            {"evidence", "question", "focus", "viewpoint", "detail", "budget"},
            set(view["transformations"][0]["inputs"]),
        )
        evidence_ids = {
            json.loads(line).get("id") for line in snapshot.read_text().splitlines()
        }
        for item in view["units"] + view["connections"] + view["omissions"]:
            self.assertTrue(set(item["evidence"]).issubset(evidence_ids))

    def test_question_focus_viewpoint_detail_and_budget_are_operational(self) -> None:
        snapshot = self.representation_fixture()

        def compile_view(name: str, arguments: tuple[str, ...]) -> dict[str, object]:
            output = self.repository.root / f"{name}.json"
            result, _, error = self.invoke(
                "compile", *arguments, "--output", str(output)
            )
            self.assertEqual(0, result, error)
            return json.loads(output.read_text())

        compiler = compile_view(
            "compiler", self.compile_arguments(snapshot, "compiler")
        )
        client = compile_view("client", self.compile_arguments(snapshot, "client"))
        self.assertNotEqual(
            [unit["id"] for unit in compiler["units"]],
            [unit["id"] for unit in client["units"]],
        )

        other_arguments = list(self.compile_arguments(snapshot, "client"))
        other_arguments[other_arguments.index("docs/design.md")] = "docs/other.md"
        other = compile_view("other", tuple(other_arguments))
        self.assertNotEqual(compiler["subject"], other["subject"])

        file_id = next(
            json.loads(line)["id"]
            for line in snapshot.read_text().splitlines()
            if json.loads(line).get("path") == "docs/design.md"
            and json.loads(line).get("type") == "file"
        )
        id_arguments = list(self.compile_arguments(snapshot, "compiler"))
        id_arguments[id_arguments.index("docs/design.md")] = file_id
        focused_by_id = compile_view("focused-by-id", tuple(id_arguments))
        self.assertEqual(compiler["subject"], focused_by_id["subject"])

        evidence_arguments = list(self.compile_arguments(snapshot, "compiler"))
        evidence_arguments[evidence_arguments.index("topology")] = "evidence-list"
        evidence_view = compile_view("evidence-list", tuple(evidence_arguments))
        self.assertEqual(
            {"matched-by"}, {edge["type"] for edge in evidence_view["connections"]}
        )
        self.assertNotIn("repository", {unit["type"] for unit in evidence_view["units"]})

        detailed_arguments = list(self.compile_arguments(snapshot, "compiler"))
        detailed_arguments[detailed_arguments.index("summary")] = "evidence"
        detailed = compile_view("detailed", tuple(detailed_arguments))
        self.assertTrue(all("source" in unit for unit in detailed["units"]))

        bounded = compile_view(
            "bounded", self.compile_arguments(snapshot, "compiler", budget=2)
        )
        self.assertEqual(2, len(bounded["units"]))
        self.assertTrue(bounded["omissions"])

    def test_saved_view_renders_and_explains_inclusion_and_omission(self) -> None:
        snapshot = self.representation_fixture()
        view_path = self.repository.root / "view.json"
        result, _, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, budget=3),
            "--output",
            str(view_path),
        )
        self.assertEqual(0, result, error)
        view = json.loads(view_path.read_text())

        result, output, error = self.invoke("map", "--view", str(view_path))
        self.assertEqual(0, result, error)
        self.assertIn("Viewpoint: topology", output)
        self.assertIn("Omitted:", output)

        included_id = view["units"][-1]["id"]
        result, output, error = self.invoke(
            "explain", included_id, "--view", str(view_path)
        )
        self.assertEqual(0, result, error)
        self.assertIn("Decision: included", output)
        self.assertIn("Evidence:", output)

        omitted_id = view["omissions"][0]["unit"]
        result, output, error = self.invoke(
            "explain", omitted_id, "--view", str(view_path)
        )
        self.assertEqual(0, result, error)
        self.assertIn("Decision: omitted", output)
        self.assertIn("max-visible-units", output)

    def test_unsupported_intent_produces_diagnostic_view(self) -> None:
        snapshot = self.representation_fixture()
        arguments = list(self.compile_arguments(snapshot, "compiler"))
        arguments[arguments.index("locate-evidence")] = "infer-causality"
        output = self.repository.root / "diagnostic.json"

        result, _, error = self.invoke(
            "compile", *arguments, "--output", str(output)
        )

        self.assertEqual(0, result, error)
        view = json.loads(output.read_text())
        self.assertEqual([], view["units"])
        self.assertEqual("unsupported-intent", view["diagnostics"][0]["code"])

    def historical_fixture(self) -> Path:
        self.repository.write(
            "tower/search.py", "def collect():\n    return 'search evidence'\n"
        )
        self.repository.write("docs/search.md", "Search evidence is inspected here.\n")
        self.repository.commit("introduce search evidence")
        self.repository.write(
            "tower/search.py",
            "def collect():\n    return 'rg --json search evidence'\n",
        )
        self.repository.write(
            "tests/test_search.py", "def test_search():\n    assert 'rg --json'\n"
        )
        self.repository.commit("collect rg evidence with a test")
        snapshot = self.repository.root / "history.jsonl"
        result, _, error = self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )
        self.assertEqual(0, result, error)
        return snapshot

    def historical_arguments(
        self, snapshot: Path, viewpoint: str, budget: int = 100
    ) -> tuple[str, ...]:
        return (
            "--evidence",
            str(snapshot),
            "--question",
            "Which files and revisions define search evidence?",
            "--intent",
            "locate-evidence",
            "--term",
            "search evidence",
            "--term",
            "rg --json",
            "--focus",
            ".",
            "--viewpoint",
            viewpoint,
            "--detail",
            "evidence",
            "--budget-units",
            str(budget),
        )

    def test_index_collects_inspectable_git_history_and_line_provenance(self) -> None:
        snapshot = self.historical_fixture()
        records = [json.loads(line) for line in snapshot.read_text().splitlines()]

        self.assertEqual(1, sum(record["type"] == "revision" for record in records))
        commits = [record for record in records if record["type"] == "commit"]
        self.assertEqual(2, len(commits))
        latest = next(
            record
            for record in commits
            if record["subject"] == "collect rg evidence with a test"
        )
        self.assertEqual(
            ["tests/test_search.py", "tower/search.py"], latest["changed_files"]
        )
        self.assertIn("+    return 'rg --json search evidence'", latest["diff"])
        attribution = next(
            record
            for record in records
            if record["type"] == "line-attribution"
            and record["path"] == "tower/search.py"
            and record["line"] == 2
        )
        self.assertEqual(latest["id"], attribution["commit_id"])

        result, output, error = self.invoke(
            "evidence", latest["id"], "--evidence", str(snapshot), "--json"
        )
        self.assertEqual(0, result, error)
        self.assertEqual(latest["diff"], json.loads(output)["diff"])

    def test_uncommitted_lines_are_not_attributed_to_the_base_revision(self) -> None:
        self.repository.write("source.py", "stable\nold evidence\n")
        self.repository.commit("base")
        self.repository.write("source.py", "stable\nnew evidence\n")
        snapshot = self.repository.root / "dirty.jsonl"

        result, _, error = self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )

        self.assertEqual(0, result, error)
        records = [json.loads(line) for line in snapshot.read_text().splitlines()]
        self.assertTrue(records[0]["workspace"]["dirty"])
        changed_span = next(
            record for record in records if record.get("text") == "new evidence"
        )
        self.assertFalse(
            any(
                record.get("type") == "line-attribution"
                and record.get("span_id") == changed_span["id"]
                for record in records
            )
        )

    def test_evidence_and_change_viewpoints_use_only_supported_relationships(self) -> None:
        snapshot = self.historical_fixture()

        views = {}
        for viewpoint in ("evidence", "change"):
            output = self.repository.root / f"{viewpoint}.json"
            result, _, error = self.invoke(
                "compile",
                *self.historical_arguments(snapshot, viewpoint),
                "--output",
                str(output),
            )
            self.assertEqual(0, result, error)
            views[viewpoint] = json.loads(output.read_text())

        self.assertEqual(
            {"contains", "matched-by"},
            {connection["type"] for connection in views["evidence"]["connections"]},
        )
        change_relationships = {
            connection["type"] for connection in views["change"]["connections"]
        }
        self.assertEqual(
            {"matched-by", "changed-in", "line-attributed-to", "changed-with"},
            change_relationships,
        )
        inferred = [
            connection
            for connection in views["change"]["connections"]
            if connection["type"] == "changed-with"
        ]
        self.assertTrue(inferred)
        self.assertTrue(
            all(connection["status"] == "historical-inference" for connection in inferred)
        )
        self.assertTrue(
            all(
                connection["status"] == "observed"
                for connection in views["change"]["connections"]
                if connection["type"] != "changed-with"
            )
        )
        result, output, error = self.invoke(
            "map", "--view", str(self.repository.root / "change.json")
        )
        self.assertEqual(0, result, error)
        self.assertIn("changed-with", output)
        self.assertIn("[historical-inference]", output)

        change = views["change"]
        golden_projection = {
            "unit_types": sorted({item["type"] for item in change["units"]}),
            "file_labels": sorted(
                item["label"] for item in change["units"] if item["type"] == "file"
            ),
            "connection_types": sorted(change_relationships),
            "inferred_connection_types": sorted(
                {
                    item["type"]
                    for item in change["connections"]
                    if item["status"] == "historical-inference"
                }
            ),
            "omission_count": len(change["omissions"]),
        }
        golden_path = Path(__file__).parent / "golden" / "milestone-3-change-view.json"
        self.assertEqual(json.loads(golden_path.read_text()), golden_projection)

    def test_unsupported_semantic_viewpoint_produces_diagnostic_view(self) -> None:
        snapshot = self.historical_fixture()
        output = self.repository.root / "unsupported.json"

        result, _, error = self.invoke(
            "compile",
            *self.historical_arguments(snapshot, "causality"),
            "--output",
            str(output),
        )

        self.assertEqual(0, result, error)
        view = json.loads(output.read_text())
        self.assertEqual([], view["units"])
        self.assertEqual("unsupported-viewpoint", view["diagnostics"][0]["code"])


if __name__ == "__main__":
    unittest.main()
