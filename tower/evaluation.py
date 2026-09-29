from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


EVALUATION_SCHEMA_VERSION = 1
CONDITIONS = ("baseline", "tower")
ACTIONS = ("query", "navigation", "transformation", "evidence-opened")


class EvaluationError(Exception):
    """An invalid evaluation request or artifact."""


def read_json(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvaluationError(f"cannot read {description} {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvaluationError(f"invalid {description} {path}: expected a JSON object")
    return value


def write_json(value: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def require_schema(value: dict[str, object], schema: str, description: str) -> None:
    if (
        value.get("schema") != schema
        or value.get("schema_version") != EVALUATION_SCHEMA_VERSION
    ):
        raise EvaluationError(f"invalid {description}: expected {schema} version 1")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise EvaluationError("invalid session timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvaluationError(f"invalid session timestamp: {value}") from error


def validate_task(task: dict[str, object]) -> None:
    require_schema(task, "tower-evaluation-task", "task")
    required = ("id", "revision", "question", "compiler_request")
    missing = [field for field in required if not task.get(field)]
    if missing:
        raise EvaluationError("invalid task: missing " + ", ".join(missing))
    request = task["compiler_request"]
    if not isinstance(request, dict):
        raise EvaluationError("invalid task: compiler_request must be an object")
    dimensions = (
        "question",
        "intent",
        "terms",
        "focus",
        "viewpoint",
        "detail",
        "budget_units",
    )
    missing_dimensions = [field for field in dimensions if not request.get(field)]
    if missing_dimensions:
        raise EvaluationError(
            "invalid task: compiler_request missing " + ", ".join(missing_dimensions)
        )


def start_session(
    task: dict[str, object],
    condition: str,
    revision: str,
    *,
    dirty: bool = False,
    now: Callable[[], str] = timestamp,
) -> dict[str, object]:
    validate_task(task)
    if condition not in CONDITIONS:
        raise EvaluationError(f"unsupported evaluation condition: {condition}")
    if revision != task["revision"]:
        raise EvaluationError(
            f"task requires revision {task['revision']}, but workspace is at {revision}"
        )
    if dirty:
        raise EvaluationError("evaluation requires a clean workspace at the pinned revision")
    return {
        "schema": "tower-evaluation-session",
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "task": {
            "id": task["id"],
            "revision": task["revision"],
            "question": task["question"],
        },
        "condition": condition,
        "started_at": now(),
        "ended_at": None,
        "elapsed_seconds": None,
        "actions": [],
        "answer": None,
    }


def validate_open_session(session: dict[str, object]) -> None:
    require_schema(session, "tower-evaluation-session", "session")
    if session.get("ended_at") is not None:
        raise EvaluationError("evaluation session is already submitted")


def record_action(
    session: dict[str, object],
    action: str,
    value: str,
    *,
    now: Callable[[], str] = timestamp,
) -> dict[str, object]:
    validate_open_session(session)
    if action not in ACTIONS:
        raise EvaluationError(f"unsupported evaluation action: {action}")
    result = dict(session)
    result["actions"] = [
        *session.get("actions", []),
        {"at": now(), "type": action, "value": value},
    ]
    return result


def submit_answer(
    session: dict[str, object],
    answer: str,
    *,
    confidence: int | None,
    now: Callable[[], str] = timestamp,
) -> dict[str, object]:
    validate_open_session(session)
    if not answer.strip():
        raise EvaluationError("answer must not be empty")
    if confidence is not None and not 0 <= confidence <= 100:
        raise EvaluationError("confidence must be between 0 and 100")
    ended_at = now()
    elapsed = (
        parse_timestamp(ended_at) - parse_timestamp(session["started_at"])
    ).total_seconds()
    if elapsed < 0:
        raise EvaluationError("session end precedes its start")
    result = dict(session)
    result.update(
        {
            "ended_at": ended_at,
            "elapsed_seconds": elapsed,
            "answer": {"text": answer.rstrip(), "confidence": confidence},
        }
    )
    return result


def score_session(
    session: dict[str, object],
    rubric: dict[str, object],
    assessment: dict[str, object],
) -> dict[str, object]:
    require_schema(session, "tower-evaluation-session", "session")
    require_schema(rubric, "tower-evaluation-rubric", "rubric")
    require_schema(assessment, "tower-evaluation-assessment", "assessment")
    if session.get("answer") is None:
        raise EvaluationError("evaluation session has no submitted answer")
    task = session.get("task", {})
    task_id = task.get("id") if isinstance(task, dict) else None
    if rubric.get("task_id") != task_id or assessment.get("task_id") != task_id:
        raise EvaluationError("session, rubric, and assessment task IDs must match")
    if rubric.get("revision") != task.get("revision"):
        raise EvaluationError("session and rubric revisions must match")
    criteria = rubric.get("criteria")
    judgments = assessment.get("criteria")
    if not isinstance(criteria, list) or not isinstance(judgments, dict):
        raise EvaluationError("invalid rubric or assessment criteria")
    criterion_ids = [item.get("id") for item in criteria if isinstance(item, dict)]
    if len(criterion_ids) != len(criteria) or set(judgments) != set(criterion_ids):
        raise EvaluationError("assessment must judge every rubric criterion exactly once")
    if not all(isinstance(value, bool) for value in judgments.values()):
        raise EvaluationError("assessment criterion judgments must be booleans")

    maximum = sum(int(item.get("points", 0)) for item in criteria)
    earned = sum(
        int(item.get("points", 0))
        for item in criteria
        if judgments[str(item["id"])]
    )
    omitted = [
        str(item["id"])
        for item in criteria
        if item.get("kind") == "required-condition" and not judgments[str(item["id"])]
    ]
    incorrect_claims = assessment.get("incorrect_claims", [])
    if not isinstance(incorrect_claims, list) or not all(
        isinstance(item, str) for item in incorrect_claims
    ):
        raise EvaluationError("assessment incorrect_claims must be a list of strings")
    counts = {action: 0 for action in ACTIONS}
    for action in session.get("actions", []):
        if isinstance(action, dict) and action.get("type") in counts:
            counts[str(action["type"])] += 1
    return {
        "schema": "tower-evaluation-score",
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "task_id": task_id,
        "revision": task.get("revision"),
        "condition": session.get("condition"),
        "correctness": {
            "earned": earned,
            "maximum": maximum,
            "percent": round(100 * earned / maximum, 2) if maximum else 0,
        },
        "omitted_conditions": omitted,
        "incorrect_claims": incorrect_claims,
        "incorrect_claim_count": len(incorrect_claims),
        "navigation": {"total_actions": sum(counts.values()), **counts},
        "elapsed_seconds": session.get("elapsed_seconds"),
        "confidence": session["answer"].get("confidence"),
    }


def compare_scores(
    baseline: dict[str, object], tower: dict[str, object]
) -> dict[str, object]:
    for score in (baseline, tower):
        require_schema(score, "tower-evaluation-score", "score")
    if baseline.get("condition") != "baseline" or tower.get("condition") != "tower":
        raise EvaluationError("comparison requires baseline and tower scores")
    if (baseline.get("task_id"), baseline.get("revision")) != (
        tower.get("task_id"),
        tower.get("revision"),
    ):
        raise EvaluationError("scores must use the same task and revision")
    return {
        "schema": "tower-evaluation-comparison",
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "task_id": baseline["task_id"],
        "revision": baseline["revision"],
        "baseline": baseline,
        "tower": tower,
        "tower_minus_baseline": {
            "correctness_points": (
                tower["correctness"]["earned"] - baseline["correctness"]["earned"]
            ),
            "omitted_conditions": (
                len(tower["omitted_conditions"])
                - len(baseline["omitted_conditions"])
            ),
            "incorrect_claims": (
                tower["incorrect_claim_count"] - baseline["incorrect_claim_count"]
            ),
            "navigation_actions": (
                tower["navigation"]["total_actions"]
                - baseline["navigation"]["total_actions"]
            ),
            "elapsed_seconds": round(
                tower["elapsed_seconds"] - baseline["elapsed_seconds"], 6
            ),
        },
    }
