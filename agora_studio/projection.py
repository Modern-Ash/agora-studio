"""Strict consumer of the AI-SDLC Studio projection contract (agora-ai-sdlc/studio-projection/v1).

Studio validates the normalized aggregate returned by Agora Core. It never imports a flavor, parses
Method Pack, profile or policy Markdown, or turns presentation hints into authority.
"""

from __future__ import annotations

import copy
import re
from typing import Mapping

PROJECTION_SCHEMA = "agora-ai-sdlc/studio-projection/v1"
PROJECTION_SCHEMA_PREFIX = "agora-ai-sdlc/studio-projection/"
SECTIONS = (
    "flavor",
    "profiles",
    "lifecycle",
    "clarifications",
    "provenance",
    "separation",
    "metrics",
)
SNAPSHOT = re.compile(r"[0-9a-f]{64}\Z")
_OPAQUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
_UNSAFE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:sk|gh[pousr])[_-][A-Za-z0-9_-]{8,}"
    r"|\b[a-z][a-z0-9+.-]*://"
    r"|(?<![A-Za-z0-9._-])(?:~?/|\.{1,2}/|\\\\|[A-Za-z]:[\\/])\S*",
    re.IGNORECASE,
)
_MAX_DEPTH = 12
_MAX_STRING = 2_000


class ProjectionError(Exception):
    """The aggregate is incompatible or unsafe; the message is safe for the browser."""

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


def _fail(code: str, reason: str) -> ProjectionError:
    return ProjectionError(f"projection.{code}", reason)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise _fail("malformed", f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail("malformed", f"{label} must be a non-empty string")
    return value


def _scan_safe(value: object, depth: int = 0) -> None:
    if depth > _MAX_DEPTH:
        raise _fail("unsafe-content", "the projection nests too deeply")
    if isinstance(value, str):
        if len(value) > _MAX_STRING or _UNSAFE.search(value):
            raise _fail(
                "unsafe-content",
                "the projection contains a path, endpoint or credential-shaped value",
            )
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _fail("malformed", "object keys must be strings")
            _scan_safe(key, depth + 1)
            _scan_safe(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _scan_safe(item, depth + 1)
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise _fail("malformed", "numbers must be finite")
    elif value is not None and not isinstance(value, (bool, int)):
        raise _fail("malformed", "the projection must be JSON data")


def _check_envelope(name: str, section: object) -> Mapping[str, object]:
    envelope = _mapping(section, f"section {name}")
    status = envelope.get("status")
    if status == "available":
        if envelope.get("value") is None:
            raise _fail("malformed", f"available section {name} has no value")
    elif status == "unavailable":
        reason = _mapping(envelope.get("reason"), f"section {name} reason")
        _text(reason.get("code"), f"section {name} reason code")
        _text(reason.get("message"), f"section {name} reason message")
        if "value" in envelope:
            raise _fail("malformed", f"unavailable section {name} must not carry a value")
    else:
        raise _fail("malformed", f"section {name} has an unsupported availability status")
    return envelope


def _check_lifecycle(value: object) -> None:
    lifecycle = _mapping(value, "lifecycle value")
    states = lifecycle.get("states")
    if not isinstance(states, list) or not states:
        raise _fail("lifecycle-contradiction", "lifecycle declares no states")
    ids = [
        _text(_mapping(state, "lifecycle state").get("id"), "lifecycle state id")
        for state in states
    ]
    if len(set(ids)) != len(ids):
        raise _fail("lifecycle-contradiction", "lifecycle state ids must be unique")
    current = _text(lifecycle.get("current_state"), "lifecycle current_state")
    if current not in ids:
        raise _fail("lifecycle-contradiction", "the current state is not a declared state")
    terminal = lifecycle.get("terminal_state")
    if terminal is not None and terminal not in ids:
        raise _fail("lifecycle-contradiction", "the terminal state is not a declared state")
    transitions = lifecycle.get("transitions", [])
    if not isinstance(transitions, list):
        raise _fail("malformed", "lifecycle transitions must be a list")
    for transition in transitions:
        item = _mapping(transition, "lifecycle transition")
        _text(item.get("source"), "lifecycle transition source")
        _text(item.get("target"), "lifecycle transition target")


def validate_projection(
    payload: object,
    *,
    selection_id: str,
    project: str,
    swarm_id: str,
    work_id: str,
) -> dict[str, object]:
    """Return a defensive copy of a compatible aggregate or fail closed."""
    aggregate = _mapping(payload, "the projection")
    schema = aggregate.get("schema")
    if schema != PROJECTION_SCHEMA:
        if isinstance(schema, str) and schema.startswith(PROJECTION_SCHEMA_PREFIX):
            raise _fail(
                "unsupported-version",
                f"Studio supports {PROJECTION_SCHEMA}; found {schema[:100]}",
            )
        raise _fail("malformed", "the payload is not an AI-SDLC projection")
    _text(aggregate.get("generated_at"), "generated_at")

    identity = _mapping(aggregate.get("project"), "project identity")
    snapshot = identity.get("snapshot")
    if not isinstance(snapshot, str) or SNAPSHOT.fullmatch(snapshot) is None:
        raise _fail("malformed-snapshot", "the snapshot must be a SHA-256 hex digest")
    supplied_selection = identity.get("selection_id")
    if not isinstance(supplied_selection, str) or _OPAQUE.fullmatch(supplied_selection) is None:
        raise _fail("malformed", "the selection id is not an opaque identifier")
    supplied = (
        supplied_selection,
        identity.get("id"),
        identity.get("swarm_id"),
        identity.get("work_id"),
    )
    if supplied != (selection_id, project, swarm_id, work_id):
        raise _fail("identity-mismatch", "the projection does not describe the selected work")

    for name in SECTIONS:
        if name not in aggregate:
            raise _fail("missing-section", f"required section {name} is missing")
        envelope = _check_envelope(name, aggregate[name])
        if name == "lifecycle" and envelope["status"] == "available":
            _check_lifecycle(envelope["value"])
    presentation = _mapping(aggregate.get("presentation"), "presentation")
    if presentation.get("authoritative") is not False:
        raise _fail("presentation-authoritative", "presentation hints must be non-authoritative")

    _scan_safe(aggregate)
    return copy.deepcopy(dict(aggregate))
