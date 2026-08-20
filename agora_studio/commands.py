"""HTTP-to-Core adapter for governed Agora Studio commands."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .core import ProjectSelection

APPROVE_GATE_SCHEMA = "agora/application/approve-gate-command/v1"
_SLUG = re.compile(r"[a-z][a-z0-9-]*")
_MAX_REASON = 4_000
_MAX_REFERENCES = 100
_MAX_REFERENCE_LENGTH = 2_000


class CommandAdapterError(Exception):
    """A stable Core command failure safe to expose over loopback HTTP."""

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class GateApprovalRequest:
    gate_id: str
    actor_id: str
    decision: str
    reason: str
    expected_state: str
    evidence_references: tuple[str, ...]
    authentication: Mapping[str, str] | None


class GateCommandGateway(Protocol):
    def approve_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]: ...


def normalize_gate_approval(payload: object) -> GateApprovalRequest:
    if not isinstance(payload, dict):
        raise CommandAdapterError("invalid_request", "the JSON body must be an object")
    allowed = {
        "schema",
        "gate_id",
        "actor_id",
        "decision",
        "reason",
        "expected_state",
        "evidence_references",
        "authentication",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise CommandAdapterError("invalid_request", f"unknown command field: {sorted(unknown)[0]}")
    if payload.get("schema") != APPROVE_GATE_SCHEMA:
        raise CommandAdapterError(
            "command.version-incompatible",
            f"Studio requires command schema {APPROVE_GATE_SCHEMA}",
        )
    values: dict[str, str] = {}
    for field in ("gate_id", "actor_id", "decision", "reason", "expected_state"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CommandAdapterError("invalid_request", f"command field {field} is required")
        values[field] = value.strip()
    if not _SLUG.fullmatch(values["gate_id"]):
        raise CommandAdapterError("invalid_request", "gate_id must be a safe Agora slug")
    if len(values["actor_id"]) > 256 or any(
        character in values["actor_id"] for character in ("/", "\\", "\x00")
    ):
        raise CommandAdapterError("invalid_request", "actor_id is invalid")
    if values["decision"] not in {"approved", "rejected"}:
        raise CommandAdapterError("invalid_request", "decision must be approved or rejected")
    if len(values["reason"]) > _MAX_REASON:
        raise CommandAdapterError("invalid_request", "reason is longer than 4000 characters")
    if not _SLUG.fullmatch(values["expected_state"]):
        raise CommandAdapterError("invalid_request", "expected_state must be a safe Agora slug")

    references = payload.get("evidence_references", [])
    if not isinstance(references, list) or len(references) > _MAX_REFERENCES:
        raise CommandAdapterError(
            "invalid_request", "evidence_references must be a bounded JSON array"
        )
    if any(
        not isinstance(reference, str)
        or not reference.strip()
        or len(reference) > _MAX_REFERENCE_LENGTH
        or "\x00" in reference
        for reference in references
    ):
        raise CommandAdapterError("invalid_request", "evidence_references are invalid")

    authentication = payload.get("authentication")
    if authentication is not None:
        if not isinstance(authentication, dict) or any(
            key not in {"algorithm", "fingerprint", "signature"}
            or not isinstance(value, str)
            or not value
            for key, value in authentication.items()
        ):
            raise CommandAdapterError("invalid_request", "authentication material is invalid")
        if set(authentication) != {"algorithm", "fingerprint", "signature"}:
            raise CommandAdapterError("invalid_request", "authentication material is incomplete")

    return GateApprovalRequest(
        gate_id=values["gate_id"],
        actor_id=values["actor_id"],
        decision=values["decision"],
        reason=values["reason"],
        expected_state=values["expected_state"],
        evidence_references=tuple(reference.strip() for reference in references),
        authentication=authentication,
    )


class CoreCommandGateway:
    """Invoke Agora Core application services without terminal-command indirection."""

    def approve_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]:
        try:
            from agora.application import (
                AgoraApplicationError,
                AgoraCommandService,
                ApproveGateCommand,
            )
        except ImportError as error:
            raise CommandAdapterError(
                "command.version-incompatible",
                "Agora Core with AgoraCommandService is not available in this environment",
            ) from error

        command = ApproveGateCommand(
            project_identity=selection.project,
            swarm_id=swarm_id,
            work_id=work_id,
            gate_id=request.gate_id,
            actor_id=request.actor_id,
            decision=request.decision,
            reason=request.reason,
            expected_state=request.expected_state,
            evidence_references=request.evidence_references,
            authentication=request.authentication,
        )
        try:
            projection = AgoraCommandService.from_path(selection.path).approve_gate(command)
        except AgoraApplicationError as error:
            safe = error.to_dict()
            raise CommandAdapterError(str(safe["code"]), str(safe["message"])) from error
        except Exception as error:
            raise CommandAdapterError(
                "command.persistence-failed",
                "Agora Core could not complete the gate decision",
            ) from error
        return projection.to_dict()
