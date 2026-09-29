from __future__ import annotations

import unittest

from tower.evaluation import (
    EvaluationError,
    compare_scores,
    record_action,
    score_session,
    start_session,
    submit_answer,
)


REVISION = "a" * 40


def task() -> dict[str, object]:
    return {
        "schema": "tower-evaluation-task",
        "schema_version": 1,
        "id": "compiler-frame",
        "revision": REVISION,
        "question": "How does each compiler input affect the view?",
        "compiler_request": {
            "question": "How does each compiler input affect the view?",
            "intent": "locate-evidence",
            "terms": ["question", "focus"],
            "focus": "tower/representation.py",
            "viewpoint": "topology",
            "detail": "evidence",
            "budget_units": 8,
        },
    }


def rubric() -> dict[str, object]:
    return {
        "schema": "tower-evaluation-rubric",
        "schema_version": 1,
        "task_id": "compiler-frame",
        "revision": REVISION,
        "claims": [
            {
                "id": "claim-frame",
                "text": "The complete request is retained in the frame.",
                "evidence": [
                    {"path": "tower/representation.py", "start_line": 187, "end_line": 197}
                ],
            }
        ],
        "distractors": [
            {"path": "tower/representation.py", "start_line": 26, "end_line": 28}
        ],
        "criteria": [
            {
                "id": "claim-frame",
                "kind": "claim",
                "text": "States that the frame retains every input.",
                "points": 2,
            },
            {
                "id": "condition-terms",
                "kind": "required-condition",
                "text": "Notes that explicit terms, not question prose, determine relevance.",
                "points": 1,
            },
        ],
    }


class EvaluationTest(unittest.TestCase):
    def session(self, condition: str = "baseline") -> dict[str, object]:
        times = iter(("2026-01-01T00:00:00Z", "2026-01-01T00:00:02Z"))
        session = start_session(task(), condition, REVISION, now=lambda: next(times))
        session = record_action(
            session, "query", "rg compiler", now=lambda: next(times)
        )
        return submit_answer(
            session,
            "The frame retains each input.",
            confidence=80,
            now=lambda: "2026-01-01T00:00:05Z",
        )

    def test_session_records_actions_answer_and_elapsed_time(self) -> None:
        session = self.session()

        self.assertEqual("baseline", session["condition"])
        self.assertEqual(
            [{"at": "2026-01-01T00:00:02Z", "type": "query", "value": "rg compiler"}],
            session["actions"],
        )
        self.assertEqual(5, session["elapsed_seconds"])
        self.assertEqual(80, session["answer"]["confidence"])

    def test_session_rejects_wrong_revision_and_changes_after_submission(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "task requires revision"):
            start_session(task(), "tower", "b" * 40)
        with self.assertRaisesRegex(EvaluationError, "clean workspace"):
            start_session(task(), "tower", REVISION, dirty=True)

        with self.assertRaisesRegex(EvaluationError, "already submitted"):
            record_action(self.session(), "query", "another query")

    def test_scoring_counts_required_omissions_and_navigation(self) -> None:
        assessment = {
            "schema": "tower-evaluation-assessment",
            "schema_version": 1,
            "task_id": "compiler-frame",
            "criteria": {"claim-frame": True, "condition-terms": False},
            "incorrect_claims": ["Question prose is interpreted semantically."],
        }

        score = score_session(self.session(), rubric(), assessment)

        self.assertEqual(
            {"earned": 2, "maximum": 3, "percent": 66.67}, score["correctness"]
        )
        self.assertEqual(["condition-terms"], score["omitted_conditions"])
        self.assertEqual(1, score["incorrect_claim_count"])
        self.assertEqual(1, score["navigation"]["query"])
        self.assertEqual(1, score["navigation"]["total_actions"])

    def test_assessment_must_judge_every_criterion(self) -> None:
        assessment = {
            "schema": "tower-evaluation-assessment",
            "schema_version": 1,
            "task_id": "compiler-frame",
            "criteria": {"claim-frame": True},
            "incorrect_claims": [],
        }

        with self.assertRaisesRegex(EvaluationError, "every rubric criterion"):
            score_session(self.session(), rubric(), assessment)

    def test_scoring_rejects_ground_truth_from_another_revision(self) -> None:
        assessment = {
            "schema": "tower-evaluation-assessment",
            "schema_version": 1,
            "task_id": "compiler-frame",
            "criteria": {"claim-frame": True, "condition-terms": True},
            "incorrect_claims": [],
        }
        wrong_rubric = {**rubric(), "revision": "b" * 40}

        with self.assertRaisesRegex(EvaluationError, "rubric revisions"):
            score_session(self.session(), wrong_rubric, assessment)

    def test_comparison_reports_tower_minus_baseline_without_claiming_usefulness(self) -> None:
        assessment = {
            "schema": "tower-evaluation-assessment",
            "schema_version": 1,
            "task_id": "compiler-frame",
            "criteria": {"claim-frame": True, "condition-terms": False},
            "incorrect_claims": [],
        }
        baseline = score_session(self.session(), rubric(), assessment)
        tower_assessment = {
            **assessment,
            "criteria": {"claim-frame": True, "condition-terms": True},
        }
        tower = score_session(self.session("tower"), rubric(), tower_assessment)

        comparison = compare_scores(baseline, tower)

        self.assertEqual(1, comparison["tower_minus_baseline"]["correctness_points"])
        self.assertEqual(-1, comparison["tower_minus_baseline"]["omitted_conditions"])
        self.assertNotIn("useful", comparison)


if __name__ == "__main__":
    unittest.main()
