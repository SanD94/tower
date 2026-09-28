from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Sequence

from tower.evidence import search_snapshot


REPRESENTATION_SCHEMA_VERSION = 1
SUPPORTED_INTENT = "locate-evidence"
SUPPORTED_VIEWPOINTS = ("topology", "evidence-list", "evidence", "change")
SUPPORTED_DETAILS = ("summary", "evidence")


class RepresentationError(Exception):
    """An invalid representation request or artifact."""


def stable_id(kind: str, *parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()
    return f"{kind}-{hashlib.sha256(encoded).hexdigest()[:20]}"


def record_by_id(
    records: Sequence[dict[str, object]], identifier: str
) -> dict[str, object] | None:
    return next((record for record in records if record.get("id") == identifier), None)


def resolve_focus(
    records: Sequence[dict[str, object]], focus: str
) -> dict[str, object]:
    by_identifier = record_by_id(records, focus)
    if by_identifier is not None:
        return by_identifier

    normalized = focus.removeprefix("./").rstrip("/") or "."
    if normalized == ".":
        return records[0]
    matches = [
        record
        for record in records
        if record.get("type") == "file" and record.get("path") == normalized
    ]
    if len(matches) == 1:
        return matches[0]
    raise RepresentationError(f"focus not found in evidence: {focus}")


def evidence_reference(record: dict[str, object]) -> str:
    identifier = record.get("id")
    if not isinstance(identifier, str):
        raise RepresentationError("evidence snapshot has a record without an ID; re-index it")
    return identifier


def source_label(record: dict[str, object], detail: str) -> str:
    if record.get("type") == "snapshot":
        workspace = record.get("workspace", {})
        return Path(str(workspace.get("root", "repository"))).name
    if record.get("type") == "file":
        return str(record["path"])
    if record.get("type") == "commit":
        return f"{str(record['oid'])[:12]} {record['subject']}"
    text = str(record.get("text", ""))
    return text if detail == "evidence" else text.lstrip("# ").strip()


def unit(
    role: str,
    record: dict[str, object],
    detail: str,
    *,
    label: str | None = None,
    provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence_id = evidence_reference(record)
    result: dict[str, object] = {
        "id": stable_id("unit", role, evidence_id, provenance or {}),
        "type": role,
        "label": label or source_label(record, detail),
        "evidence": [evidence_id],
    }
    if detail == "evidence":
        result["source"] = {
            key: record[key]
            for key in (
                "path",
                "span",
                "text",
                "oid",
                "parents",
                "author",
                "authored_at",
                "subject",
                "changed_files",
                "diff",
                "collector",
            )
            if key in record
        }
    if provenance:
        result["provenance"] = provenance
    return result


def connection(
    relationship: str,
    source: dict[str, object],
    target: dict[str, object],
    evidence: Sequence[str],
    *,
    status: str = "observed",
) -> dict[str, object]:
    return {
        "id": stable_id("connection", relationship, source["id"], target["id"]),
        "type": relationship,
        "source": source["id"],
        "target": target["id"],
        "evidence": list(dict.fromkeys(evidence)),
        "status": status,
    }


def matching_file(
    records: Sequence[dict[str, object]], match: dict[str, object]
) -> dict[str, object]:
    file_record = next(
        (
            record
            for record in records
            if record.get("type") == "file" and record.get("path") == match["path"]
        ),
        None,
    )
    if file_record is None:
        raise RepresentationError(f"file evidence not found for match: {match['path']}")
    return file_record


def file_for_record(
    records: Sequence[dict[str, object]], record: dict[str, object]
) -> dict[str, object] | None:
    if record.get("type") == "file":
        return record
    file_id = record.get("file_id")
    return record_by_id(records, str(file_id)) if file_id else None


def matching_headings(
    records: Sequence[dict[str, object]], path: str
) -> list[dict[str, object]]:
    results = search_snapshot(records, r"^#{1,6}\s+")
    return sorted(
        (result for result in results if result["path"] == path),
        key=lambda result: int(result["span"]["start"]["line"]),
    )


def compile_representation(
    records: Sequence[dict[str, object]],
    *,
    question: str,
    intent: str,
    terms: Sequence[str],
    focus: str,
    viewpoint: str,
    detail: str,
    budget_units: int,
) -> dict[str, object]:
    if detail not in SUPPORTED_DETAILS:
        raise RepresentationError(f"unsupported detail: {detail}")
    if budget_units < 1:
        raise RepresentationError("budget-units must be at least 1")
    if not terms:
        raise RepresentationError("at least one question term is required")

    focus_record = resolve_focus(records, focus)
    focus_id = evidence_reference(focus_record)
    frame = {
        "evidence": evidence_reference(records[0]),
        "question": {"text": question, "intent": intent, "terms": list(terms)},
        "focus": focus_id,
        "viewpoint": viewpoint,
        "detail": detail,
        "budget": {"max_visible_units": budget_units},
        "assumptions": [
            "Question relevance is limited to the explicit terms; free text is not interpreted."
        ],
    }
    result: dict[str, object] = {
        "schema": "tower-representation-ir",
        "schema_version": REPRESENTATION_SCHEMA_VERSION,
        "subject": focus_id,
        "frame": frame,
        "units": [],
        "connections": [],
        "regions": [],
        "omissions": [],
        "diagnostics": [],
        "transformations": [
            {
                "name": "compile",
                "deterministic": True,
                "inputs": ["evidence", "question", "focus", "viewpoint", "detail", "budget"],
            }
        ],
    }
    if intent != SUPPORTED_INTENT:
        result["diagnostics"] = [
            {
                "code": "unsupported-intent",
                "message": f"intent is not supported by deterministic compilation: {intent}",
            }
        ]
        return result
    if viewpoint not in SUPPORTED_VIEWPOINTS:
        result["diagnostics"] = [
            {
                "code": "unsupported-viewpoint",
                "message": (
                    "viewpoint is not supported by collected textual and historical "
                    f"evidence: {viewpoint}"
                ),
            }
        ]
        return result

    focus_file = file_for_record(records, focus_record)
    scope_path = str(focus_file["path"]) if focus_file else None
    snapshot = records[0]
    repository_unit = unit("repository", snapshot, detail)
    focus_role = {
        "snapshot": "repository",
        "file": "file",
        "span": "span",
    }.get(str(focus_record.get("type")), str(focus_record.get("type")))
    focus_unit = unit(focus_role, focus_record, detail)

    matches: list[tuple[dict[str, object], str]] = []
    matches_by_term: list[list[dict[str, object]]] = []
    for term in terms:
        term_matches = [
            match
            for match in search_snapshot(records, re.escape(term))
            if scope_path is None or match["path"] == scope_path
        ]
        matches_by_term.append(
            sorted(
                term_matches,
                key=lambda match: (
                    str(match["path"]),
                    int(match["span"]["start"]["line"]),
                    int(match["span"]["start"]["byte_column"]),
                ),
            )
        )
    for index in range(max((len(items) for items in matches_by_term), default=0)):
        for term, term_matches in zip(terms, matches_by_term):
            if index < len(term_matches):
                matches.append((term_matches[index], term))

    candidates: list[dict[str, object]] = [focus_unit]
    candidate_connections: list[dict[str, object]] = []
    if viewpoint == "topology":
        if focus_record.get("type") != "snapshot":
            candidates.append(repository_unit)
            candidate_connections.append(
                connection("contains", repository_unit, focus_unit, [focus_id])
            )
        headings = matching_headings(records, scope_path) if scope_path else []
        heading_units: dict[str, dict[str, object]] = {}
        for match, term in matches:
            line = int(match["span"]["start"]["line"])
            preceding = [
                heading
                for heading in headings
                if int(heading["span"]["start"]["line"]) <= line
            ]
            parent = focus_unit
            if preceding:
                heading = preceding[-1]
                heading_id = str(heading["id"])
                if heading_id not in heading_units:
                    heading_record = record_by_id(records, heading_id)
                    if heading_record is None:
                        raise RepresentationError(f"heading evidence not found: {heading_id}")
                    heading_units[heading_id] = unit("heading", heading_record, detail)
                    candidates.append(heading_units[heading_id])
                    candidate_connections.append(
                        connection(
                            "contains",
                            focus_unit,
                            heading_units[heading_id],
                            [focus_id, heading_id],
                        )
                    )
                parent = heading_units[heading_id]
            match_record = record_by_id(records, str(match["id"]))
            if match_record is None:
                raise RepresentationError(f"match evidence not found: {match['id']}")
            match_unit = unit(
                "match",
                match_record,
                detail,
                provenance={
                    "matched_by": term,
                    "match_span": match["span"],
                    "collector": match["collector"],
                },
            )
            candidates.append(match_unit)
            candidate_connections.append(
                connection("contains", parent, match_unit, [str(match["id"])])
            )
    elif viewpoint == "evidence-list":
        for match, term in matches:
            match_record = record_by_id(records, str(match["id"]))
            if match_record is None:
                raise RepresentationError(f"match evidence not found: {match['id']}")
            match_unit = unit(
                "match",
                match_record,
                detail,
                provenance={
                    "matched_by": term,
                    "match_span": match["span"],
                    "collector": match["collector"],
                },
            )
            candidates.append(match_unit)
            candidate_connections.append(
                connection("matched-by", focus_unit, match_unit, [str(match["id"])])
            )
    elif viewpoint == "evidence":
        file_units: dict[str, dict[str, object]] = {}
        for match, term in matches:
            file_record = matching_file(records, match)
            file_id = evidence_reference(file_record)
            if file_id not in file_units:
                file_units[file_id] = (
                    focus_unit if file_id == focus_id else unit("file", file_record, detail)
                )
                if file_id != focus_id:
                    candidates.append(file_units[file_id])
                if focus_record.get("type") == "snapshot":
                    candidate_connections.append(
                        connection(
                            "contains",
                            focus_unit,
                            file_units[file_id],
                            [focus_id, file_id],
                        )
                    )
            match_record = record_by_id(records, str(match["id"]))
            if match_record is None:
                raise RepresentationError(f"match evidence not found: {match['id']}")
            match_unit = unit(
                "match",
                match_record,
                detail,
                provenance={
                    "matched_by": term,
                    "match_span": match["span"],
                    "collector": match["collector"],
                },
            )
            candidates.append(match_unit)
            candidate_connections.append(
                connection(
                    "matched-by",
                    file_units[file_id],
                    match_unit,
                    [str(match["id"])],
                )
            )
    else:
        commits = {
            str(record["id"]): record
            for record in records
            if record.get("type") == "commit"
        }
        attributions = {
            str(record["span_id"]): record
            for record in records
            if record.get("type") == "line-attribution"
        }
        file_units: dict[str, dict[str, object]] = {}
        commit_units: dict[str, dict[str, object]] = {}
        for match, term in matches:
            file_record = matching_file(records, match)
            file_id = evidence_reference(file_record)
            if file_id not in file_units:
                file_units[file_id] = (
                    focus_unit if file_id == focus_id else unit("file", file_record, detail)
                )
                if file_id != focus_id:
                    candidates.append(file_units[file_id])
            match_record = record_by_id(records, str(match["id"]))
            if match_record is None:
                raise RepresentationError(f"match evidence not found: {match['id']}")
            match_unit = unit(
                "match",
                match_record,
                detail,
                provenance={
                    "matched_by": term,
                    "match_span": match["span"],
                    "collector": match["collector"],
                },
            )
            candidates.append(match_unit)
            candidate_connections.append(
                connection("matched-by", file_units[file_id], match_unit, [str(match["id"])])
            )
            attribution = attributions.get(str(match["id"]))
            if attribution is not None:
                commit_record = commits.get(str(attribution["commit_id"]))
                if commit_record is not None:
                    commit_id = evidence_reference(commit_record)
                    if commit_id not in commit_units:
                        commit_units[commit_id] = unit("commit", commit_record, detail)
                        candidates.append(commit_units[commit_id])
                    candidate_connections.append(
                        connection(
                            "line-attributed-to",
                            match_unit,
                            commit_units[commit_id],
                            [str(attribution["id"])],
                        )
                    )

        matching_paths = {str(match["path"]) for match, _ in matches}
        files_by_path = {
            str(record["path"]): record
            for record in records
            if record.get("type") == "file"
        }
        for commit_id, commit_record in commits.items():
            changed_paths = set(str(path) for path in commit_record["changed_files"])
            relevant_paths = sorted(changed_paths & matching_paths)
            if not relevant_paths:
                continue
            if commit_id not in commit_units:
                commit_units[commit_id] = unit("commit", commit_record, detail)
                candidates.append(commit_units[commit_id])
            for path in relevant_paths:
                file_record = files_by_path[path]
                file_id = evidence_reference(file_record)
                if file_id not in file_units:
                    file_units[file_id] = unit("file", file_record, detail)
                    candidates.append(file_units[file_id])
                candidate_connections.append(
                    connection(
                        "changed-in",
                        file_units[file_id],
                        commit_units[commit_id],
                        [commit_id],
                    )
                )
                for companion_path in sorted(changed_paths - {path}):
                    companion_record = files_by_path.get(companion_path)
                    if companion_record is None:
                        continue
                    companion_id = evidence_reference(companion_record)
                    if companion_id not in file_units:
                        file_units[companion_id] = unit("file", companion_record, detail)
                        candidates.append(file_units[companion_id])
                    source_path, target_path = sorted((path, companion_path))
                    source_id = evidence_reference(files_by_path[source_path])
                    target_id = evidence_reference(files_by_path[target_path])
                    candidate_connections.append(
                        connection(
                            "changed-with",
                            file_units[source_id],
                            file_units[target_id],
                            [commit_id],
                            status="historical-inference",
                        )
                    )

    visible = candidates[:budget_units]
    visible_ids = {candidate["id"] for candidate in visible}
    result["units"] = visible
    visible_connections: dict[str, dict[str, object]] = {}
    for item in candidate_connections:
        if item["source"] not in visible_ids or item["target"] not in visible_ids:
            continue
        identifier = str(item["id"])
        if identifier in visible_connections:
            visible_connections[identifier]["evidence"] = list(
                dict.fromkeys(
                    visible_connections[identifier]["evidence"] + item["evidence"]
                )
            )
        else:
            visible_connections[identifier] = item
    result["connections"] = list(visible_connections.values())
    omitted_ids = {candidate["id"] for candidate in candidates[budget_units:]}
    for candidate in candidates[budget_units:]:
        hidden_unit = deepcopy(candidate)
        if detail == "summary":
            record = record_by_id(records, str(candidate["evidence"][0]))
            if record is not None:
                detailed = unit(
                    str(candidate["type"]),
                    record,
                    "evidence",
                    label=str(candidate["label"]),
                    provenance=candidate.get("provenance"),
                )
                hidden_unit = detailed
        result["omissions"].append(
            {
                "unit": candidate["id"],
                "type": candidate["type"],
                "evidence": candidate["evidence"],
                "reason": "max-visible-units",
                "hidden_unit": hidden_unit,
                "connections": [
                    deepcopy(item)
                    for item in candidate_connections
                    if candidate["id"] in (item["source"], item["target"])
                    and (
                        item["source"] in visible_ids | omitted_ids
                        and item["target"] in visible_ids | omitted_ids
                    )
                ],
            }
        )
    return result


def visible_claim_ids(view: dict[str, object]) -> list[str]:
    return [
        str(item["id"])
        for item in [*view["units"], *view["connections"]]
    ]


def transformation_record(
    name: str,
    *,
    before: Sequence[str],
    after: Sequence[str],
    inputs: dict[str, object],
) -> dict[str, object]:
    before_set = set(before)
    after_set = set(after)
    return {
        "name": name,
        "deterministic": True,
        "inputs": inputs,
        "claims": {
            "added": sorted(after_set - before_set),
            "retained": sorted(before_set & after_set),
            "omitted": sorted(before_set - after_set),
        },
    }


def find_unit(view: dict[str, object], identifier: str) -> dict[str, object]:
    found = next(
        (item for item in view["units"] if item.get("id") == identifier), None
    )
    if found is None:
        raise RepresentationError(f"visible unit not found in representation: {identifier}")
    return found


def refine_representation(
    view: dict[str, object],
    identifier: str,
    *,
    detail: str,
    budget_units: int,
) -> dict[str, object]:
    if detail not in SUPPORTED_DETAILS:
        raise RepresentationError(f"unsupported detail: {detail}")
    if budget_units < 1:
        raise RepresentationError("budget-units must be at least 1")
    if view.get("regions"):
        raise RepresentationError(
            "representation already has a refined region; collapse it before refining again"
        )
    find_unit(view, identifier)
    before = visible_claim_ids(view)
    result = deepcopy(view)
    visible_ids = {str(item["id"]) for item in result["units"]}
    omissions = {
        str(item["unit"]): item
        for item in result["omissions"]
        if isinstance(item.get("hidden_unit"), dict)
    }
    graph: dict[str, list[tuple[str, dict[str, object]]]] = {}
    for omission in omissions.values():
        for edge in omission.get("connections", []):
            source = str(edge["source"])
            target = str(edge["target"])
            graph.setdefault(source, []).append((target, edge))
            graph.setdefault(target, []).append((source, edge))

    promoted: list[str] = []
    queue: deque[str] = deque([identifier])
    visited = {identifier}
    while queue and len(promoted) < budget_units - 1:
        current = queue.popleft()
        for neighbor, _ in graph.get(current, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            if neighbor in omissions:
                promoted.append(neighbor)
                queue.append(neighbor)
                if len(promoted) == budget_units - 1:
                    break

    promoted_set = set(promoted)
    added_connections: dict[str, dict[str, object]] = {}
    for promoted_id in promoted:
        hidden = deepcopy(omissions[promoted_id]["hidden_unit"])
        if detail == "summary":
            hidden.pop("source", None)
        result["units"].append(hidden)
        visible_ids.add(promoted_id)
    for omission in omissions.values():
        for edge in omission.get("connections", []):
            if edge["source"] in visible_ids and edge["target"] in visible_ids:
                added_connections[str(edge["id"])] = deepcopy(edge)
    existing_connections = {str(item["id"]) for item in result["connections"]}
    result["connections"].extend(
        edge
        for edge_id, edge in added_connections.items()
        if edge_id not in existing_connections
    )

    previous_omissions = deepcopy(result["omissions"])
    result["omissions"] = [
        item for item in result["omissions"] if str(item["unit"]) not in promoted_set
    ]
    ports = [
        {
            "connection": str(edge["id"]),
            "type": str(edge["type"]),
            "direction": "out" if edge["source"] == identifier else "in",
            "outside": str(edge["target"] if edge["source"] == identifier else edge["source"]),
        }
        for edge in view["connections"]
        if identifier in (edge["source"], edge["target"])
    ]
    region_id = stable_id(
        "region", identifier, detail, budget_units, len(result["transformations"])
    )
    result.setdefault("regions", []).append(
        {
            "id": region_id,
            "boundary": identifier,
            "members": [identifier, *promoted],
            "ports": ports,
            "detail": detail,
            "budget": {"max_visible_units": budget_units},
            "inverse": {
                "remove_units": promoted,
                "remove_connections": sorted(
                    set(added_connections) - existing_connections
                ),
                "restore_omissions": previous_omissions,
            },
        }
    )
    after = visible_claim_ids(result)
    result["transformations"].append(
        transformation_record(
            "refine",
            before=before,
            after=after,
            inputs={
                "unit": identifier,
                "detail": detail,
                "budget": {"max_visible_units": budget_units},
                "region": region_id,
            },
        )
    )
    return result


def collapse_representation(
    view: dict[str, object], region_id: str
) -> dict[str, object]:
    region = next(
        (item for item in view.get("regions", []) if item.get("id") == region_id), None
    )
    if region is None:
        raise RepresentationError(f"region not found in representation: {region_id}")
    before = visible_claim_ids(view)
    result = deepcopy(view)
    inverse = region["inverse"]
    remove_units = set(inverse["remove_units"])
    remove_connections = set(inverse["remove_connections"])
    result["units"] = [
        item for item in result["units"] if item["id"] not in remove_units
    ]
    result["connections"] = [
        item
        for item in result["connections"]
        if item["id"] not in remove_connections
    ]
    result["omissions"] = deepcopy(inverse["restore_omissions"])
    result["regions"] = [
        item for item in result["regions"] if item["id"] != region_id
    ]
    after = visible_claim_ids(result)
    result["transformations"].append(
        transformation_record(
            "collapse",
            before=before,
            after=after,
            inputs={"region": region_id},
        )
    )
    return result


def filtered_representation(
    view: dict[str, object],
    *,
    name: str,
    inputs: dict[str, object],
    retained_connections: Sequence[dict[str, object]],
    required_unit_ids: set[str],
) -> dict[str, object]:
    before = visible_claim_ids(view)
    result = deepcopy(view)
    retained_ids = {str(item["id"]) for item in retained_connections}
    removed_units = [
        item for item in result["units"] if str(item["id"]) not in required_unit_ids
    ]
    removed_connections = [
        item for item in result["connections"] if str(item["id"]) not in retained_ids
    ]
    result["units"] = [
        item for item in result["units"] if str(item["id"]) in required_unit_ids
    ]
    result["connections"] = list(deepcopy(retained_connections))
    for item in removed_units:
        result["omissions"].append(
            {
                "unit": item["id"],
                "type": item["type"],
                "evidence": item["evidence"],
                "reason": name,
                "hidden_unit": deepcopy(item),
                "connections": [
                    deepcopy(edge)
                    for edge in removed_connections
                    if item["id"] in (edge["source"], edge["target"])
                ],
            }
        )
    result["regions"] = []
    after = visible_claim_ids(result)
    result["transformations"].append(
        transformation_record(name, before=before, after=after, inputs=inputs)
    )
    return result


def trace_representation(
    view: dict[str, object], identifier: str
) -> dict[str, object]:
    find_unit(view, identifier)
    connected = {identifier}
    queue = deque([identifier])
    while queue:
        current = queue.popleft()
        for edge in view["connections"]:
            if current not in (edge["source"], edge["target"]):
                continue
            neighbor = str(
                edge["target"] if edge["source"] == current else edge["source"]
            )
            if neighbor not in connected:
                connected.add(neighbor)
                queue.append(neighbor)
    subject_units = {
        str(item["id"])
        for item in view["units"]
        if view["subject"] in item["evidence"]
    }
    connected.update(subject_units)
    edges = [
        item
        for item in view["connections"]
        if item["source"] in connected and item["target"] in connected
    ]
    return filtered_representation(
        view,
        name="trace",
        inputs={"unit": identifier},
        retained_connections=edges,
        required_unit_ids=connected,
    )


def project_representation(
    view: dict[str, object], relationship: str
) -> dict[str, object]:
    edges = [item for item in view["connections"] if item["type"] == relationship]
    if not edges:
        raise RepresentationError(
            f"relationship type not found in representation: {relationship}"
        )
    required = {
        str(endpoint)
        for edge in edges
        for endpoint in (edge["source"], edge["target"])
    }
    required.update(
        str(item["id"])
        for item in view["units"]
        if view["subject"] in item["evidence"]
    )
    return filtered_representation(
        view,
        name="project",
        inputs={"relationship_type": relationship},
        retained_connections=edges,
        required_unit_ids=required,
    )


def write_representation(view: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(view, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_representation(path: Path) -> dict[str, object]:
    try:
        view = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RepresentationError(f"cannot read representation {path}: {error}") from error
    if view.get("schema") != "tower-representation-ir" or view.get("schema_version") != 1:
        raise RepresentationError(f"unsupported representation schema in {path}")
    return view


def render_representation(view: dict[str, object]) -> str:
    frame = view["frame"]
    lines = [
        f"Question: {frame['question']['text']}",
        f"Focus: {view['subject']}",
        f"Viewpoint: {frame['viewpoint']} | Detail: {frame['detail']} | Units: {len(view['units'])}/{frame['budget']['max_visible_units']}",
    ]
    for item in view["units"]:
        lines.append(f"[{item['type']}] {item['id']}  {item['label']}")
    for item in view["connections"]:
        status = "" if item["status"] == "observed" else f" [{item['status']}]"
        lines.append(
            f"  {item['source']} --{item['type']}--> {item['target']}{status}"
        )
    if view["omissions"]:
        reasons = ", ".join(
            sorted({str(item["reason"]) for item in view["omissions"]})
        )
        lines.append(f"Omitted: {len(view['omissions'])} relevant units ({reasons})")
    for diagnostic in view["diagnostics"]:
        lines.append(f"Diagnostic: {diagnostic['message']}")
    return "\n".join(lines)


def explain(view: dict[str, object], identifier: str) -> str:
    visible = next(
        (item for item in view["units"] if item.get("id") == identifier), None
    )
    if visible is not None:
        provenance = visible.get("provenance", {})
        reason = (
            f"explicit question term {provenance['matched_by']!r}"
            if "matched_by" in provenance
            else "required focus or containment context"
        )
        return "\n".join(
            (
                f"Unit: {identifier}",
                "Decision: included",
                f"Reason: {reason}",
                f"Evidence: {', '.join(visible['evidence'])}",
            )
        )
    omitted = next(
        (item for item in view["omissions"] if item.get("unit") == identifier), None
    )
    if omitted is not None:
        return "\n".join(
            (
                f"Unit: {identifier}",
                "Decision: omitted",
                f"Reason: {omitted['reason']}",
                f"Evidence: {', '.join(omitted['evidence'])}",
            )
        )
    raise RepresentationError(f"unit not found in representation: {identifier}")
