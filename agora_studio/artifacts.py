"""Validated artifacts, evidence, and approvals projection for one selected work item."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Mapping

from .lifecycle import _SLUG, _regular_file, _summary_fields


class ArtifactsError(Exception):
    """A safe artifacts/evidence/approvals request or resolution failure."""

    def __init__(self, kind: str, reason: str):
        self.kind = kind
        self.reason = reason
        super().__init__(reason)


def normalize_artifacts_query(query: Mapping[str, object] | None) -> dict[str, str]:
    values = query or {}
    allowed = {"swarm", "work"}
    unknown = set(values) - allowed
    if unknown:
        raise ArtifactsError(
            "invalid_query", f"unknown artifacts query field: {sorted(unknown)[0]}"
        )
    normalized: dict[str, str] = {}
    for key in allowed:
        raw = values.get(key)
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                raise ArtifactsError(
                    "invalid_query", f"artifacts query field {key} must be provided once"
                )
            raw = raw[0]
        if not isinstance(raw, str) or not raw:
            raise ArtifactsError("invalid_query", f"artifacts query field {key} is required")
        if len(raw) > 128 or any(unicodedata.category(character) == "Cc" for character in raw):
            raise ArtifactsError("invalid_query", f"artifacts query field {key} is invalid")
        if not _SLUG.fullmatch(raw):
            raise ArtifactsError(
                "invalid_query", f"artifacts query field {key} must be a safe Agora slug"
            )
        normalized[key] = raw
    return normalized


def _table_rows(project: Path, relative: Path, column_count: int) -> list[list[str]]:
    """Read a bounded durable Markdown table's data rows, skipping heading and separator rows."""
    path = _regular_file(project, relative)
    rows: list[list[str]] = []
    seen_separator = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != column_count:
            continue
        if not seen_separator:
            # The first table line is the heading row; the second is the `---` separator.
            if all(set(cell) <= {"-", ":"} and cell for cell in cells):
                seen_separator = True
            continue
        rows.append(cells)
    return rows


def _artifact_rows(project: Path, swarm: str, work: str) -> list[dict[str, object]]:
    relative = Path(".agora") / "swarms" / swarm / "work" / work / "artifacts.md"
    rows = _table_rows(project, relative, 4)
    return [
        {
            "id": f"artifact-{index}",
            "kind": kind,
            "uri": uri,
            "produced_by": produced_by,
            "timestamp": timestamp,
        }
        for index, (kind, uri, produced_by, timestamp) in enumerate(rows)
    ]


def _evidence_rows(project: Path, swarm: str, work: str) -> list[dict[str, object]]:
    relative = Path(".agora") / "swarms" / swarm / "work" / work / "evidence.md"
    rows = _table_rows(project, relative, 5)
    return [
        {
            "id": f"evidence-{index}",
            "type": kind,
            "result": result,
            "artifact_references": [
                reference.strip() for reference in references.split(",") if reference.strip()
            ],
            "produced_by": produced_by,
            "timestamp": timestamp,
        }
        for index, (kind, result, references, produced_by, timestamp) in enumerate(rows)
    ]


def _approval_rows(project: Path, swarm: str, work: str) -> list[dict[str, object]]:
    relative = Path(".agora") / "swarms" / swarm / "work" / work / "approvals.md"
    rows = _table_rows(project, relative, 4)
    return [
        {
            "id": f"approval-{index}",
            "role": role,
            "approved_by": approved_by,
            "note": note,
            "timestamp": timestamp,
        }
        for index, (role, approved_by, note, timestamp) in enumerate(rows)
    ]


def _traceability(event: Mapping[str, object]) -> dict[str, object]:
    return {
        "session_id": event.get("session_id"),
        "tool_run_id": event.get("tool_run_id"),
        "source": event.get("source"),
        "type": event.get("type"),
        "timestamp": event.get("timestamp"),
    }


def _attach_traceability(
    rows: list[dict[str, object]], events: list[dict[str, object]], key_of_row, key_of_event
) -> None:
    """Attach traceability only where a durable identifier is exact: match same-key rows and events
    positionally, in the order both durably occur. Never infer across differing kinds or by time alone."""
    grouped_rows: dict[tuple, list[dict[str, object]]] = {}
    for row in rows:
        grouped_rows.setdefault(key_of_row(row), []).append(row)
    grouped_events: dict[tuple, list[dict[str, object]]] = {}
    for event in events:
        key = key_of_event(event)
        if key is None:
            continue
        grouped_events.setdefault(key, []).append(event)
    for key, matched_rows in grouped_rows.items():
        matched_events = grouped_events.get(key, [])
        for row, event in zip(matched_rows, matched_events):
            has_identifier = event.get("session_id") or event.get("tool_run_id")
            row["traceability"] = _traceability(event) if has_identifier else None
    for row in rows:
        row.setdefault("traceability", None)


def build_artifacts(store: object, query: Mapping[str, object] | None) -> dict[str, object]:
    """Build one combined, normalized artifacts/evidence/approvals projection from exact durable records."""
    normalized = normalize_artifacts_query(query)
    selection = store.selection
    if selection is None:
        raise ArtifactsError(
            "project_required", "Select a local Agora project before loading artifacts data."
        )

    work_records = store._cli.execute("work", selection.path).data
    work = next(
        (
            item
            for item in work_records
            if isinstance(item, dict)
            and item.get("id") == normalized["work"]
            and item.get("swarm_id") == normalized["swarm"]
        ),
        None,
    )
    if work is None:
        raise ArtifactsError("not_found", "the selected work does not exist in the selected swarm")

    diagnostics: list[str] = []
    try:
        artifacts = _artifact_rows(selection.path, normalized["swarm"], normalized["work"])
    except (OSError, UnicodeError, ValueError) as error:
        artifacts = []
        diagnostics.append(f"Artifacts are unavailable: {error}")
    try:
        evidence = _evidence_rows(selection.path, normalized["swarm"], normalized["work"])
    except (OSError, UnicodeError, ValueError) as error:
        evidence = []
        diagnostics.append(f"Evidence is unavailable: {error}")
    try:
        approvals = _approval_rows(selection.path, normalized["swarm"], normalized["work"])
    except (OSError, UnicodeError, ValueError) as error:
        approvals = []
        diagnostics.append(f"Approvals are unavailable: {error}")

    activity_result = store.activity(
        {"swarm": normalized["swarm"], "work": normalized["work"], "limit": "500"}
    )
    events = activity_result.get("events", []) if isinstance(activity_result, dict) else []

    def artifact_event_key(event: Mapping[str, object]) -> tuple | None:
        if event.get("type") != "artifact.added":
            return None
        fields = _summary_fields(event.get("summary"))
        if "kind" not in fields or "uri" not in fields:
            return None
        return (fields["kind"], fields["uri"])

    def evidence_event_key(event: Mapping[str, object]) -> tuple | None:
        if event.get("type") != "evidence.added":
            return None
        fields = _summary_fields(event.get("summary"))
        if "type" not in fields or "result" not in fields:
            return None
        return (fields["type"], fields["result"])

    def approval_event_key(event: Mapping[str, object]) -> tuple | None:
        if event.get("type") != "approval.added":
            return None
        fields = _summary_fields(event.get("summary"))
        if "role" not in fields:
            return None
        return (fields["role"],)

    _attach_traceability(
        artifacts, events, lambda row: (row["kind"], row["uri"]), artifact_event_key
    )
    _attach_traceability(
        evidence, events, lambda row: (row["type"], row["result"]), evidence_event_key
    )
    _attach_traceability(approvals, events, lambda row: (row["role"],), approval_event_key)

    required_roles = (
        work.get("approval_roles") if isinstance(work.get("approval_roles"), list) else []
    )
    required_roles = [role for role in required_roles if isinstance(role, str)]
    satisfied_role_set = {row["role"] for row in approvals}
    satisfaction = [
        {"role": role, "satisfied": role in satisfied_role_set} for role in required_roles
    ]

    return {
        "selection": selection.as_dict(),
        "scope": {
            "swarm_id": normalized["swarm"],
            "work_id": normalized["work"],
            "title": work.get("title"),
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "approvals": {
            "required_roles": required_roles,
            "records": approvals,
            "satisfaction": satisfaction,
        },
        "availability": {
            "artifacts": True,
            "evidence": True,
            "approvals": True,
            "partial": bool(diagnostics),
        },
        "diagnostics": diagnostics,
    }
