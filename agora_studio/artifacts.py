"""HTTP presentation mapping for Core-owned work materials."""

from __future__ import annotations

import unicodedata
from typing import Mapping

from .core import CoreGatewayError, ProjectStore
from .lifecycle import _SLUG


class ArtifactsError(Exception):
    """A safe work-material request error."""

    def __init__(self, kind: str, reason: str):
        self.kind = kind
        self.reason = reason
        super().__init__(reason)


def normalize_artifacts_query(query: Mapping[str, object] | None) -> dict[str, str]:
    values = query or {}
    unknown = set(values) - {"swarm", "work"}
    if unknown:
        raise ArtifactsError(
            "invalid_query", f"unknown artifacts query field: {sorted(unknown)[0]}"
        )
    normalized: dict[str, str] = {}
    for key in ("swarm", "work"):
        raw = values.get(key)
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                raise ArtifactsError(
                    "invalid_query", f"artifacts query field {key} must be provided once"
                )
            raw = raw[0]
        if (
            not isinstance(raw, str)
            or not raw
            or len(raw) > 128
            or any(unicodedata.category(character) == "Cc" for character in raw)
            or not _SLUG.fullmatch(raw)
        ):
            raise ArtifactsError(
                "invalid_query", f"artifacts query field {key} must be a safe Agora slug"
            )
        normalized[key] = raw
    return normalized


def build_artifacts(store: ProjectStore, query: Mapping[str, object] | None) -> dict[str, object]:
    """Return exact Core materials without reading or interpreting durable files."""
    normalized = normalize_artifacts_query(query)
    selection = store.selection
    if selection is None:
        raise ArtifactsError(
            "project_required", "Select a local Agora project before loading artifacts data."
        )
    swarm, work_id = normalized["swarm"], normalized["work"]
    try:
        work = store.gateway.get_work_item(selection.path, swarm, work_id)
        lifecycle = store.gateway.lifecycle(selection.path, swarm, work_id)
        artifacts = store.gateway.artifacts(selection.path, swarm, work_id)
        evidence = store.gateway.evidence(selection.path, swarm, work_id)
        approvals = store.gateway.approvals(selection.path, swarm, work_id)
        traceability = store.gateway.traceability(selection.path, swarm, work_id)
    except CoreGatewayError as error:
        if error.code == "read.resource-not-found":
            raise ArtifactsError("not_found", error.reason) from error
        raise

    required_roles: list[str] = []
    missing_roles: list[str] = []
    for transition in lifecycle.get("transitions", []):
        if not isinstance(transition, dict) or transition.get("source") != lifecycle.get(
            "current_state"
        ):
            continue
        for role in transition.get("required_approval_roles", []):
            if isinstance(role, str) and role not in required_roles:
                required_roles.append(role)
        for blocker in transition.get("blockers", []):
            if not isinstance(blocker, dict) or blocker.get("category") != "approval":
                continue
            for role in blocker.get("references", []):
                if isinstance(role, str) and role not in missing_roles:
                    missing_roles.append(role)
    approval_records = [{**item, "approved_by": item.get("actor")} for item in approvals]
    return {
        "schema": "agora-studio/api/work-materials/v1",
        "selection": selection.as_dict(),
        "scope": {"swarm_id": swarm, "work_id": work_id, "title": work.get("title")},
        "artifacts": artifacts,
        "evidence": evidence,
        "approvals": {
            "schema": "agora-studio/api/approval-status/v1",
            "required_roles": required_roles,
            "missing_roles": missing_roles,
            "records": approval_records,
        },
        "traceability": traceability,
        "availability": {
            "artifacts": True,
            "evidence": True,
            "approvals": True,
            "traceability": True,
            "partial": False,
        },
        "diagnostics": [],
    }
