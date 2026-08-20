"""Validated lifecycle, Activity-path, and specification-history projection."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Mapping

from .git_history import GitHistoryReader, GitReadError

_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SUMMARY_VALUE = re.compile(r"(?:^|\s)([a-z][a-z0-9_-]*)=([^\s]+)")
_MAX_MARKDOWN_BYTES = 262_144
_MAX_METHOD_CHILDREN = 64


class LifecycleError(Exception):
    """A safe lifecycle request or resolution failure."""

    def __init__(self, kind: str, reason: str):
        self.kind = kind
        self.reason = reason
        super().__init__(reason)


def normalize_lifecycle_query(
    query: Mapping[str, object] | None, *, detail: bool = False
) -> dict[str, str]:
    values = query or {}
    allowed = {"swarm", "work", *(("revision",) if detail else ())}
    unknown = set(values) - allowed
    if unknown:
        raise LifecycleError(
            "invalid_query", f"unknown lifecycle query field: {sorted(unknown)[0]}"
        )
    normalized: dict[str, str] = {}
    for key in allowed:
        raw = values.get(key)
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                raise LifecycleError(
                    "invalid_query", f"lifecycle query field {key} must be provided once"
                )
            raw = raw[0]
        if not isinstance(raw, str) or not raw:
            raise LifecycleError("invalid_query", f"lifecycle query field {key} is required")
        if len(raw) > 128 or any(unicodedata.category(character) == "Cc" for character in raw):
            raise LifecycleError("invalid_query", f"lifecycle query field {key} is invalid")
        if key in ("swarm", "work") and not _SLUG.fullmatch(raw):
            raise LifecycleError(
                "invalid_query", f"lifecycle query field {key} must be a safe Agora slug"
            )
        if key == "revision" and raw != "working-tree" and not re.fullmatch(r"[0-9a-f]{40}", raw):
            raise LifecycleError("invalid_query", "lifecycle revision identifier is invalid")
        normalized[key] = raw
    return normalized


def _parse_scalar(value: str) -> object:
    value = value.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in ("null", "~"):
            return None
        if re.fullmatch(r"-?[0-9]+", value):
            return int(value)
        return value.strip("\"'")


def parse_front_matter(text: str) -> dict[str, object]:
    """Parse the bounded, single-line scalar subset used by Agora records."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("front matter is missing")
    result: dict[str, object] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line or line[:1].isspace():
            raise ValueError("front matter contains an unsupported field")
        key, value = line.split(":", 1)
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", key):
            raise ValueError("front matter contains an invalid key")
        result[key] = _parse_scalar(value)
    raise ValueError("front matter is not terminated")


def _regular_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError("path is outside the reviewed boundary")
    root = root.resolve(strict=True)
    unresolved = root / relative
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("symbolic links are outside the reviewed boundary")
    resolved = unresolved.resolve(strict=True)
    resolved.relative_to(root)
    if not resolved.is_file():
        raise ValueError("record is not a regular file")
    if resolved.stat().st_size > _MAX_MARKDOWN_BYTES:
        raise ValueError("record exceeds the bounded read size")
    return resolved


def _read_front_matter(root: Path, relative: Path) -> dict[str, object]:
    path = _regular_file(root, relative)
    return parse_front_matter(path.read_text(encoding="utf-8"))


def _summary_fields(summary: object) -> dict[str, str]:
    if not isinstance(summary, str):
        return {}
    return {match.group(1): match.group(2) for match in _SUMMARY_VALUE.finditer(summary)}


def _spec_uris(project: Path, swarm: str, work: str) -> list[str]:
    relative = Path(".agora") / "swarms" / swarm / "work" / work / "artifacts.md"
    path = _regular_file(project, relative)
    uris: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == "spec" and cells[1].startswith("repo://"):
            uris.append(cells[1].strip("`"))
    return list(dict.fromkeys(uris))


def _gate_blockers(gate: dict[str, object], work: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    if gate.get("require-all-criteria") is True:
        criteria = (
            set((work.get("acceptance_criteria") or {}).keys())
            if isinstance(work.get("acceptance_criteria"), dict)
            else set()
        )
        satisfied = set(work.get("satisfied_criteria") or [])
        if not criteria.issubset(satisfied):
            blockers.append("acceptance criteria are incomplete")
    if gate.get("require-required-artifacts") is True:
        required = set(work.get("required_artifacts") or [])
        present = set(work.get("artifact_kinds") or [])
        missing = sorted(required - present)
        if missing:
            blockers.append(f"required artifacts missing: {', '.join(missing)}")
    if gate.get("require-successful-evidence") is True and "success" not in (
        work.get("evidence_results") or []
    ):
        blockers.append("successful evidence is missing")
    required_roles = set(gate.get("required-approval-roles") or [])
    approval_roles = set(work.get("approval_roles") or [])
    missing_roles = sorted(required_roles - approval_roles)
    if missing_roles:
        blockers.append(f"approvals missing: {', '.join(missing_roles)}")
    return blockers


def _method_projection(
    project: Path, method_id: str, work: dict[str, object]
) -> tuple[dict[str, object], list[str]]:
    diagnostics: list[str] = []
    method_root = project / ".agora" / "methods" / method_id
    try:
        method = _read_front_matter(project, Path(".agora") / "methods" / method_id / "METHOD.md")
    except (OSError, UnicodeError, ValueError) as error:
        return (
            {
                "available": False,
                "id": method_id,
                "states": [],
                "transitions": [],
                "current_state": work.get("state"),
                "initial_state": None,
                "terminal_state": None,
            },
            [f"Method topology unavailable: {error}"],
        )
    states = method.get("work-states")
    if not isinstance(states, list) or not all(
        isinstance(value, str) and value for value in states
    ):
        return (
            {
                "available": False,
                "id": method_id,
                "states": [],
                "transitions": [],
                "current_state": work.get("state"),
                "initial_state": None,
                "terminal_state": None,
            },
            ["Method topology unavailable: work-states is invalid"],
        )
    transition_dir = method_root / "transitions"
    transition_paths = sorted(transition_dir.glob("*.md")) if transition_dir.is_dir() else []
    if len(transition_paths) > _MAX_METHOD_CHILDREN:
        transition_paths = transition_paths[:_MAX_METHOD_CHILDREN]
        diagnostics.append("Method transitions were truncated at the bounded file limit.")
    gates: dict[str, dict[str, object]] = {}
    gate_dir = method_root / "gates"
    gate_paths = sorted(gate_dir.glob("*.md")) if gate_dir.is_dir() else []
    for path in gate_paths[:_MAX_METHOD_CHILDREN]:
        try:
            record = _read_front_matter(project, path.relative_to(project))
            gate_id = record.get("id")
            if record.get("schema") == "agora/gate/v1" and isinstance(gate_id, str):
                gates[gate_id] = record
            else:
                diagnostics.append(f"Ignored malformed gate record: {path.name}")
        except (OSError, UnicodeError, ValueError):
            diagnostics.append(f"Ignored unreadable gate record: {path.name}")
    transitions: list[dict[str, object]] = []
    state_set = set(states)
    current = work.get("state")
    for index, path in enumerate(transition_paths):
        try:
            record = _read_front_matter(project, path.relative_to(project))
            source, target, roles = record.get("from"), record.get("to"), record.get("roles")
            if (
                record.get("schema") != "agora/transition/v1"
                or source not in state_set
                or target not in state_set
                or not isinstance(roles, list)
                or not all(isinstance(role, str) for role in roles)
            ):
                raise ValueError("transition fields are invalid")
            gate_id = record.get("gate") if isinstance(record.get("gate"), str) else None
            gate = gates.get(gate_id, {}) if gate_id is not None else {}
            required_approval_roles = gate.get("required-approval-roles", [])
            if not isinstance(required_approval_roles, list) or not all(
                isinstance(role, str) for role in required_approval_roles
            ):
                required_approval_roles = []
            blockers = _gate_blockers(gate, work) if gate_id in gates and source == current else []
            if source == current and work.get("operational_status") not in (None, "active"):
                reason = (
                    work.get("status_reason")
                    if isinstance(work.get("status_reason"), str)
                    else "no reason recorded"
                )
                blockers.append(f"work is {work.get('operational_status')}: {reason}")
            transitions.append(
                {
                    "id": f"transition-{index}-{source}-{target}",
                    "from": source,
                    "to": target,
                    "roles": roles,
                    "gate": gate_id,
                    "required_approval_roles": required_approval_roles,
                    "blockers": blockers,
                    "available": source == current and not blockers,
                    "source": f"repo://{path.relative_to(project).as_posix()}",
                }
            )
        except (OSError, UnicodeError, ValueError):
            diagnostics.append(f"Ignored malformed transition record: {path.name}")
    incoming = {transition["to"] for transition in transitions}
    initial = next(
        (state for state in states if state not in incoming), states[0] if states else None
    )
    terminal = method.get("terminal-state") if method.get("terminal-state") in state_set else None
    return (
        {
            "available": True,
            "id": method_id,
            "name": method.get("name") if isinstance(method.get("name"), str) else method_id,
            "states": [
                {
                    "id": value,
                    "initial": value == initial,
                    "current": value == current,
                    "terminal": value == terminal,
                }
                for value in states
            ],
            "transitions": transitions,
            "current_state": current,
            "initial_state": initial,
            "terminal_state": terminal,
            "source": f"repo://.agora/methods/{method_id}/METHOD.md",
        },
        diagnostics,
    )


def _activity_projection(
    events: list[dict[str, object]], current_state: object
) -> dict[str, object]:
    traversals: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    for event in events:
        fields = _summary_fields(event.get("summary"))
        if event.get("type") == "work.transitioned" and "from" in fields and "to" in fields:
            traversals.append(
                {
                    "id": f"traversal-{len(traversals)}",
                    "from": fields["from"],
                    "to": fields["to"],
                    "timestamp": event.get("timestamp"),
                    "actor": event.get("actor"),
                    "session_id": event.get("session_id"),
                    "source": event.get("source"),
                    "role": fields.get("role"),
                }
            )
        event_type = str(event.get("type") or "")
        if "handed-off" in event_type or (
            event_type.startswith("session.")
            and event_type in ("session.failed", "session.prepared")
        ):
            annotations.append(
                {
                    "id": f"annotation-{len(annotations)}",
                    "type": event_type,
                    "timestamp": event.get("timestamp"),
                    "actor": event.get("actor"),
                    "session_id": event.get("session_id"),
                    "summary": event.get("summary"),
                    "source": event.get("source"),
                    "traversal_id": None,
                }
            )
    return {"traversals": traversals, "annotations": annotations, "current_state": current_state}


def _state_at(
    revision_timestamp: object,
    traversals: list[dict[str, object]],
    initial: object,
    current: object,
) -> object:
    if revision_timestamp is None:
        return current
    state = initial
    for traversal in traversals:
        timestamp = traversal.get("timestamp")
        if (
            isinstance(timestamp, str)
            and isinstance(revision_timestamp, str)
            and timestamp <= revision_timestamp
        ):
            state = traversal.get("to")
    return state


def build_lifecycle(
    store: object, query: Mapping[str, object] | None, git: GitHistoryReader | None = None
) -> dict[str, object]:
    """Build one combined normalized projection from exact selected-work records."""
    normalized = normalize_lifecycle_query(query)
    selection = store.selection
    if selection is None:
        raise LifecycleError(
            "project_required", "Select a local Agora project before loading lifecycle data."
        )
    work_records = store._cli.execute("work", selection.path).data
    swarm_records = store._cli.execute("swarms", selection.path).data
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
        raise LifecycleError("not_found", "the selected work does not exist in the selected swarm")
    swarm = next(
        (
            item
            for item in swarm_records
            if isinstance(item, dict) and item.get("id") == normalized["swarm"]
        ),
        None,
    )
    if (
        swarm is None
        or not isinstance(swarm.get("method"), str)
        or not _SLUG.fullmatch(swarm["method"])
    ):
        raise LifecycleError("not_found", "the selected swarm or its Method Pack is unavailable")

    method, diagnostics = _method_projection(selection.path, swarm["method"], work)
    activity_result = store.activity(
        {"swarm": normalized["swarm"], "work": normalized["work"], "limit": "500"}
    )
    events = activity_result.get("events", []) if isinstance(activity_result, dict) else []
    activity = _activity_projection(events, work.get("state"))
    public_event_fields = (
        "timestamp",
        "type",
        "summary",
        "actor",
        "swarm_id",
        "work_id",
        "session_id",
        "tool_run_id",
        "source",
    )
    public_events = [{field: event.get(field) for field in public_event_fields} for event in events]

    specification: dict[str, object]
    try:
        uris = _spec_uris(selection.path, normalized["swarm"], normalized["work"])
        if not uris:
            raise GitReadError("no registered specification artifact is available")
        if len(uris) != 1:
            raise GitReadError("registered specification artifacts are ambiguous")
        reader = git or GitHistoryReader()
        _, relative = reader.resolve_repo_file(selection.path, uris[0])
        specification = {"uri": uris[0], **reader.history(selection.path, relative)}
        for revision in specification["revisions"]:
            revision["work_state"] = _state_at(
                revision.get("timestamp"),
                activity["traversals"],
                method.get("initial_state"),
                work.get("state"),
            )
            sha = revision.get("sha")
            revision["activity_refs"] = [
                {
                    "type": event.get("type"),
                    "source": event.get("source"),
                    "actor": event.get("actor"),
                    "session_id": event.get("session_id"),
                }
                for event in public_events
                if isinstance(sha, str)
                and _summary_fields(event.get("summary")).get("commit") == sha
            ]
    except (OSError, UnicodeError, ValueError, GitReadError) as error:
        specification = {
            "available": False,
            "uri": None,
            "path": None,
            "revisions": [],
            "reason": str(error),
        }
        diagnostics.append(f"Specification evolution unavailable: {error}")

    return {
        "selection": selection.as_dict(),
        "scope": {
            "swarm_id": normalized["swarm"],
            "work_id": normalized["work"],
            "title": work.get("title"),
        },
        "work": {"state": work.get("state"), "operational_status": work.get("operational_status")},
        "method": method,
        "actual_path": activity,
        "specification": specification,
        "traceability": {"events": public_events},
        "availability": {
            "method": bool(method.get("available")),
            "activity": True,
            "specification": bool(specification.get("available")),
            "partial": bool(diagnostics),
        },
        "diagnostics": diagnostics,
    }


def build_revision_detail(
    store: object, query: Mapping[str, object] | None, git: GitHistoryReader | None = None
) -> dict[str, object]:
    normalized = normalize_lifecycle_query(query, detail=True)
    projection = build_lifecycle(
        store, {"swarm": normalized["swarm"], "work": normalized["work"]}, git
    )
    specification = projection["specification"]
    known = {item["id"] for item in specification.get("revisions", [])}
    if normalized["revision"] not in known:
        raise LifecycleError(
            "not_found", "the requested revision is not available for this specification"
        )
    selection = store.selection
    reader = git or GitHistoryReader()
    detail_payload = reader.detail(selection.path, specification["path"], normalized["revision"])
    return {
        "selection": selection.as_dict(),
        "scope": projection["scope"],
        "detail": detail_payload,
    }
