"""HTTP presentation mapping for Core-owned lifecycle projections."""

from __future__ import annotations

import re
import unicodedata
from typing import Mapping

from .core import CoreGatewayError, ProjectStore

_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class LifecycleError(Exception):
    """A safe lifecycle request error."""

    def __init__(self, kind: str, reason: str):
        self.kind = kind
        self.reason = reason
        super().__init__(reason)


def normalize_lifecycle_query(query: Mapping[str, object] | None) -> dict[str, str]:
    values = query or {}
    unknown = set(values) - {"swarm", "work"}
    if unknown:
        raise LifecycleError(
            "invalid_query", f"unknown lifecycle query field: {sorted(unknown)[0]}"
        )
    normalized: dict[str, str] = {}
    for key in ("swarm", "work"):
        raw = values.get(key)
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                raise LifecycleError(
                    "invalid_query", f"lifecycle query field {key} must be provided once"
                )
            raw = raw[0]
        if (
            not isinstance(raw, str)
            or not raw
            or len(raw) > 128
            or any(unicodedata.category(character) == "Cc" for character in raw)
            or not _SLUG.fullmatch(raw)
        ):
            raise LifecycleError(
                "invalid_query", f"lifecycle query field {key} must be a safe Agora slug"
            )
        normalized[key] = raw
    return normalized


def _transition_view(item: Mapping[str, object], index: int) -> dict[str, object]:
    """Rename Core fields only for the established browser presentation contract."""
    source = item.get("source")
    target = item.get("target")
    return {
        "schema": item.get("schema"),
        "id": f"transition-{index}-{source}-{target}",
        "from": source,
        "to": target,
        "roles": item.get("authorized_roles", []),
        "gate": item.get("gate_id"),
        "required_approval_roles": item.get("required_approval_roles", []),
        "blockers": item.get("blockers", []),
        "available": item.get("available"),
    }


def build_lifecycle(store: ProjectStore, query: Mapping[str, object] | None) -> dict[str, object]:
    """Map public Core DTOs to the versioned Studio lifecycle response."""
    normalized = normalize_lifecycle_query(query)
    selection = store.selection
    if selection is None:
        raise LifecycleError(
            "project_required", "Select a local Agora project before loading lifecycle data."
        )
    swarm, work_id = normalized["swarm"], normalized["work"]
    try:
        control = store.gateway.work_control(selection.path, swarm, work_id)
        work = control["work"]
        method = store.gateway.get_method(selection.path, swarm)
        lifecycle = control["lifecycle"]
        traceability = control["traceability"]
        specification = control["specification_history"]
    except CoreGatewayError as error:
        if error.code == "read.resource-not-found":
            raise LifecycleError("not_found", error.reason) from error
        raise

    states = [
        {
            **state,
            "current": state.get("id") == lifecycle.get("current_state"),
        }
        for state in lifecycle.get("states", method.get("states", []))
        if isinstance(state, dict)
    ]
    transitions = [
        _transition_view(item, index)
        for index, item in enumerate(lifecycle.get("transitions", []))
        if isinstance(item, dict)
    ]
    diagnostics = []
    if specification.get("available") is False and specification.get("reason"):
        diagnostics.append(f"Specification history unavailable: {specification['reason']}")
    return {
        "schema": "agora-studio/api/lifecycle/v1",
        "selection": selection.as_dict(),
        "scope": {"swarm_id": swarm, "work_id": work_id, "title": work.get("title")},
        "work": {
            "schema": work.get("schema"),
            "state": work.get("state"),
            "operational_status": work.get("operational_status"),
        },
        "method": {
            "schema": method.get("schema"),
            "available": True,
            "id": method.get("id"),
            "name": method.get("name"),
            "version": method.get("version"),
            "states": states,
            "transitions": transitions,
            "gates": lifecycle.get("gates", []),
            "current_state": lifecycle.get("current_state"),
            "initial_state": next(
                (state.get("id") for state in states if state.get("initial") is True), None
            ),
            "terminal_state": lifecycle.get("terminal_state"),
        },
        "lifecycle": lifecycle,
        "specification": specification,
        "traceability": traceability,
        "gate_decision_options": control["gate_decision_options"],
        "availability": {
            "method": True,
            "traceability": True,
            "specification": bool(specification.get("available")),
            "partial": bool(diagnostics),
        },
        "diagnostics": diagnostics,
    }
