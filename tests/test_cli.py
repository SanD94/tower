from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tower.cli import main


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

    def test_worktree_edit_preserves_and_marks_recorded_evidence_stale(self) -> None:
        self.repository.write("changed.txt", "snapshot needle\n")
        self.repository.write("unchanged.txt", "stable needle\n")
        self.repository.commit()
        snapshot = self.repository.root / "evidence.jsonl"
        self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )
        recorded_snapshot = snapshot.read_bytes()
        _, output, _ = self.invoke(
            "search", "needle", "--evidence", str(snapshot), "--json"
        )
        identifiers = {
            result["path"]: result["id"] for result in json.loads(output)["results"]
        }

        self.repository.write("changed.txt", "current needle\n")

        result, output, error = self.invoke(
            "search", "needle", "--evidence", str(snapshot), "--json"
        )
        self.assertEqual(0, result, error)
        matches = {
            result["path"]: result for result in json.loads(output)["results"]
        }
        self.assertEqual("snapshot needle", matches["changed.txt"]["text"])
        self.assertTrue(matches["changed.txt"]["stale"])
        self.assertFalse(matches["unchanged.txt"]["stale"])
        self.assertEqual(identifiers["changed.txt"], matches["changed.txt"]["id"])
        self.assertEqual(identifiers["unchanged.txt"], matches["unchanged.txt"]["id"])
        self.assertNotIn("current needle", output)
        self.assertEqual(recorded_snapshot, snapshot.read_bytes())

        result, output, error = self.invoke(
            "evidence",
            identifiers["changed.txt"],
            "--evidence",
            str(snapshot),
            "--json",
        )
        self.assertEqual(0, result, error)
        self.assertTrue(json.loads(output)["stale"])

        records = [json.loads(line) for line in snapshot.read_text().splitlines()]
        changed_file = next(
            record
            for record in records
            if record.get("type") == "file" and record.get("path") == "changed.txt"
        )
        self.assertNotEqual(
            self.repository.git("hash-object", "changed.txt"), changed_file["blob_oid"]
        )

    def test_index_uses_git_blob_identity_for_tracked_modified_and_untracked_files(self) -> None:
        self.repository.write("tracked.txt", "base\n")
        self.repository.write("same-a.txt", "identical\n")
        self.repository.commit()
        self.repository.write("tracked.txt", "modified\n")
        self.repository.write("same-b.txt", "identical\n")
        self.repository.write("ignored.txt", "ignored\n")
        self.repository.write(".gitignore", "ignored.txt\n")
        snapshot = self.repository.root / "evidence.jsonl"

        result, _, error = self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )

        self.assertEqual(0, result, error)
        files = {
            record["path"]: record
            for record in map(json.loads, snapshot.read_text().splitlines())
            if record.get("type") == "file"
        }
        self.assertNotIn("ignored.txt", files)
        for path in ("tracked.txt", "same-a.txt", "same-b.txt"):
            self.assertEqual(
                self.repository.git("hash-object", path), files[path]["blob_oid"]
            )
            self.assertNotIn("content_hash", files[path])
        self.assertEqual(files["same-a.txt"]["blob_oid"], files["same-b.txt"]["blob_oid"])
        self.assertNotEqual(files["same-a.txt"]["id"], files["same-b.txt"]["id"])

    def test_checkout_marks_recorded_branch_evidence_stale(self) -> None:
        self.repository.write("branch.txt", "main branch term\n")
        main_revision = self.repository.commit("main content")
        self.repository.git("checkout", "--quiet", "-b", "other")
        self.repository.write("branch.txt", "other branch term\n")
        other_revision = self.repository.commit("other content")
        snapshot = self.repository.root / "evidence.jsonl"
        self.invoke(
            "index", "--root", str(self.repository.root), "--output", str(snapshot)
        )

        self.repository.git("checkout", "--quiet", "--detach", main_revision)
        result, output, error = self.invoke(
            "search", "branch term", "--evidence", str(snapshot), "--json"
        )

        self.assertEqual(0, result, error)
        self.assertNotIn("main branch term", output)
        self.assertIn("other branch term", output)
        self.assertTrue(json.loads(output)["results"][0]["stale"])
        header = json.loads(snapshot.read_text().splitlines()[0])
        self.assertEqual(other_revision, header["workspace"]["revision"])
        self.assertNotEqual(main_revision, header["workspace"]["revision"])

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
        self.assertEqual(
            self.repository.git("rev-parse", "HEAD"),
            view["frame"]["workspace"]["revision"],
        )
        self.assertTrue(view["frame"]["worktree"]["files"])
        self.assertTrue(
            all("blob_oid" in item for item in view["frame"]["worktree"]["files"])
        )
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

        self.repository.write(
            "docs/design.md", "# Tower\nThe previous evidence no longer applies.\n"
        )
        result, output, error = self.invoke("map", "--view", str(view_path))
        self.assertEqual(0, result, error)
        self.assertIn("Freshness: stale", output)
        self.assertIn("answer the question again", output)

        result, _, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, budget=3),
            "--output",
            str(self.repository.root / "replacement.json"),
        )
        self.assertEqual(1, result)
        self.assertIn("evidence snapshot is stale", error)
        self.assertIn("answer the question again", error)

    def test_views_lists_saved_question_frames_in_path_order(self) -> None:
        snapshot = self.representation_fixture()
        views_dir = self.repository.root / ".tower"
        first = views_dir / "a.json"
        result, _, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, "compiler", budget=4),
            "--output",
            str(first),
        )
        self.assertEqual(0, result, error)

        other_arguments = list(self.compile_arguments(snapshot, "client", budget=4))
        other_arguments[
            other_arguments.index("Where are compiler and client responsibilities?")
        ] = "Where is the client rendered?"
        second = views_dir / "b.json"
        result, _, error = self.invoke(
            "compile", *other_arguments, "--output", str(second)
        )
        self.assertEqual(0, result, error)
        (views_dir / "noise.json").write_text('{"unrelated": true}\n', encoding="utf-8")

        result, output, error = self.invoke(
            "views", "--root", str(self.repository.root), "--json"
        )
        self.assertEqual(0, result, error)
        payload = json.loads(output)
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual(str(views_dir), payload["dir"])
        self.assertEqual(1, payload["skipped"])
        self.assertEqual(
            [
                {
                    "intent": "locate-evidence",
                    "stale": False,
                    "terms": ["compiler"],
                    "text": "Where are compiler and client responsibilities?",
                },
                {
                    "intent": "locate-evidence",
                    "stale": False,
                    "terms": ["client"],
                    "text": "Where is the client rendered?",
                },
            ],
            payload["questions"],
        )

        result, output, error = self.invoke("views", "--root", str(self.repository.root))
        self.assertEqual(0, result, error)
        self.assertIn(
            "[fresh] Where are compiler and client responsibilities?\n"
            "[fresh] Where is the client rendered?",
            output,
        )
        self.assertIn("Skipped 1 file(s) that are not saved views.", output)
        self.assertLess(
            output.index("Where are compiler and client responsibilities?"),
            output.index("Where is the client rendered?"),
        )

        self.repository.write("docs/design.md", "# Changed\n")
        result, output, error = self.invoke(
            "views", "--root", str(self.repository.root), "--json"
        )
        self.assertEqual(0, result, error)
        self.assertTrue(all(item["stale"] for item in json.loads(output)["questions"]))

    def test_views_keeps_question_across_transformations(self) -> None:
        snapshot = self.representation_fixture()
        views_dir = self.repository.root / ".tower"
        original = views_dir / "bounded.json"
        result, _, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, budget=3),
            "--output",
            str(original),
        )
        self.assertEqual(0, result, error)
        boundary = json.loads(original.read_text())["units"][0]["id"]
        refined = views_dir / "refined.json"
        result, _, error = self.invoke(
            "refine",
            boundary,
            "--view",
            str(original),
            "--detail",
            "evidence",
            "--budget-units",
            "3",
            "--output",
            str(refined),
        )
        self.assertEqual(0, result, error)

        result, output, error = self.invoke(
            "views", "--root", str(self.repository.root), "--json"
        )
        self.assertEqual(0, result, error)
        payload = json.loads(output)
        self.assertEqual(
            [
                {
                    "intent": "locate-evidence",
                    "stale": False,
                    "terms": ["compiler", "client"],
                    "text": "Where are compiler and client responsibilities?",
                }
            ]
            * 2,
            payload["questions"],
        )

    def test_views_reports_missing_or_empty_tower_directory(self) -> None:
        self.repository.write("placeholder.txt")
        self.repository.commit()
        expected = self.repository.root / ".tower"

        result, output, error = self.invoke(
            "views", "--root", str(self.repository.root), "--json"
        )
        self.assertEqual(1, result)
        self.assertIn(f"no tower build found: {expected} does not exist", error)
        self.assertIn("tower index", error)

        expected.mkdir()
        result, output, error = self.invoke("views", "--root", str(self.repository.root))
        self.assertEqual(0, result, error)
        self.assertIn(f"No saved views found in {expected}", output)

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
        outputs = {}
        for viewpoint in ("evidence", "change"):
            output = Path(self.repository.temporary_directory.name).parent / (
                f"tower-{self.repository.root.name}-{viewpoint}.json"
            )
            self.addCleanup(output.unlink, missing_ok=True)
            outputs[viewpoint] = output
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
            "map", "--view", str(outputs["change"])
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

    def test_refine_is_local_and_collapse_restores_the_boundary_view(self) -> None:
        snapshot = self.representation_fixture()
        original_path = self.repository.root / "bounded.json"
        result, _, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, budget=3),
            "--output",
            str(original_path),
        )
        self.assertEqual(0, result, error)
        original = json.loads(original_path.read_text())
        boundary = original["units"][0]["id"]
        refined_path = self.repository.root / "refined.json"

        result, output, error = self.invoke(
            "refine",
            boundary,
            "--view",
            str(original_path),
            "--detail",
            "evidence",
            "--budget-units",
            "3",
            "--output",
            str(refined_path),
        )

        self.assertEqual(0, result, error)
        self.assertEqual(str(refined_path), output.strip())
        refined = json.loads(refined_path.read_text())
        self.assertEqual(original["units"], refined["units"][: len(original["units"])])
        self.assertEqual(
            original["connections"],
            refined["connections"][: len(original["connections"])],
        )
        added_units = refined["units"][len(original["units"]) :]
        self.assertEqual(2, len(added_units))
        self.assertTrue(all("source" in item for item in added_units))
        region = refined["regions"][0]
        self.assertEqual(boundary, region["boundary"])
        self.assertEqual("evidence", region["detail"])
        self.assertEqual(3, region["budget"]["max_visible_units"])
        self.assertEqual(
            {
                edge["id"]
                for edge in original["connections"]
                if boundary in (edge["source"], edge["target"])
            },
            {port["connection"] for port in region["ports"]},
        )
        refine_history = refined["transformations"][-1]
        self.assertEqual("refine", refine_history["name"])
        self.assertEqual(
            {
                item["id"]
                for item in [
                    *added_units,
                    *refined["connections"][len(original["connections"]) :],
                ]
            },
            set(refine_history["claims"]["added"]),
        )
        self.assertFalse(refine_history["claims"]["omitted"])

        collapsed_path = self.repository.root / "collapsed.json"
        result, _, error = self.invoke(
            "collapse",
            region["id"],
            "--view",
            str(refined_path),
            "--output",
            str(collapsed_path),
        )

        self.assertEqual(0, result, error)
        collapsed = json.loads(collapsed_path.read_text())
        for field in ("subject", "frame", "units", "connections", "omissions"):
            self.assertEqual(original[field], collapsed[field])
        self.assertEqual([], collapsed["regions"])
        self.assertEqual("collapse", collapsed["transformations"][-1]["name"])
        self.assertEqual(
            set(refine_history["claims"]["added"]),
            set(collapsed["transformations"][-1]["claims"]["omitted"]),
        )

    def test_refine_detail_and_budget_apply_only_to_promoted_units(self) -> None:
        snapshot = self.representation_fixture()
        original_path = self.repository.root / "bounded.json"
        result, _, error = self.invoke(
            "compile",
            *self.compile_arguments(snapshot, budget=3),
            "--output",
            str(original_path),
        )
        self.assertEqual(0, result, error)
        original = json.loads(original_path.read_text())
        boundary = original["units"][0]["id"]

        views = {}
        for detail, budget in (("summary", 2), ("evidence", 3)):
            output = self.repository.root / f"{detail}.json"
            result, _, error = self.invoke(
                "refine",
                boundary,
                "--view",
                str(original_path),
                "--detail",
                detail,
                "--budget-units",
                str(budget),
                "--output",
                str(output),
            )
            self.assertEqual(0, result, error)
            views[detail] = json.loads(output.read_text())

        summary_added = views["summary"]["units"][len(original["units"]) :]
        evidence_added = views["evidence"]["units"][len(original["units"]) :]
        self.assertEqual(1, len(summary_added))
        self.assertEqual(2, len(evidence_added))
        self.assertNotIn("source", summary_added[0])
        self.assertTrue(all("source" in item for item in evidence_added))

    def test_trace_and_project_record_every_filtered_claim(self) -> None:
        snapshot = self.historical_fixture()
        original_path = self.repository.root / "change.json"
        result, _, error = self.invoke(
            "compile",
            *self.historical_arguments(snapshot, "change"),
            "--output",
            str(original_path),
        )
        self.assertEqual(0, result, error)
        original = json.loads(original_path.read_text())
        projected_path = self.repository.root / "projected.json"

        result, _, error = self.invoke(
            "project",
            "line-attributed-to",
            "--view",
            str(original_path),
            "--output",
            str(projected_path),
        )

        self.assertEqual(0, result, error)
        projected = json.loads(projected_path.read_text())
        self.assertEqual(
            {"line-attributed-to"},
            {edge["type"] for edge in projected["connections"]},
        )
        project_history = projected["transformations"][-1]
        self.assertEqual("project", project_history["name"])
        self.assertEqual(
            len(original["units"]) + len(original["connections"]),
            sum(len(items) for items in project_history["claims"].values()),
        )
        self.assertTrue(project_history["claims"]["omitted"])

        disconnected = dict(original["units"][0])
        disconnected["id"] = "unit-disconnected"
        disconnected["evidence"] = ["evidence-disconnected"]
        original["units"].append(disconnected)
        original_path.write_text(json.dumps(original), encoding="utf-8")
        trace_from = next(
            unit["id"] for unit in original["units"] if unit["type"] == "match"
        )
        traced_path = self.repository.root / "traced.json"
        result, _, error = self.invoke(
            "trace",
            trace_from,
            "--view",
            str(original_path),
            "--output",
            str(traced_path),
        )
        self.assertEqual(0, result, error)
        traced = json.loads(traced_path.read_text())
        self.assertNotIn("unit-disconnected", {unit["id"] for unit in traced["units"]})
        self.assertIn(
            "unit-disconnected", traced["transformations"][-1]["claims"]["omitted"]
        )

        golden_projection = {
            "refine_operations": ["refine", "collapse"],
            "projected_connection_types": sorted(
                {edge["type"] for edge in projected["connections"]}
            ),
            "project_records_omissions": bool(project_history["claims"]["omitted"]),
            "trace_records_disconnected_unit": "unit-disconnected"
            in traced["transformations"][-1]["claims"]["omitted"],
        }
        golden_path = (
            Path(__file__).parent
            / "golden"
            / "milestone-4-local-transformations.json"
        )
        self.assertEqual(json.loads(golden_path.read_text()), golden_projection)


if __name__ == "__main__":
    unittest.main()
