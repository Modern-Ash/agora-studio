"""HTTP-to-Core adapter for governed Agora Studio commands."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .core import ProjectSelection

APPROVE_GATE_SCHEMA = "agora/application/approve-gate-command/v3"
AUTHORIZATION_SCHEMA = "agora/application/approve-gate-authorization/v3"
PREPARED_GATE_SCHEMA = "agora/application/prepared-gate-decision/v2"
GATE_PROJECTION_SCHEMA = "agora/application/gate-decision-projection/v2"
LIFECYCLE_SCHEMA = "agora/application/lifecycle-projection/v2"
ACTIVITY_SCHEMA = "agora/application/activity-entry/v1"
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
    transition_target: str
    role_id: str
    evidence_references: tuple[str, ...]
    precondition_digest: str | None
    authentication: Mapping[str, str] | None


class GateCommandGateway(Protocol):
    def prepare_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]: ...

    def approve_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]: ...


def normalize_gate_approval(
    payload: object, *, for_confirmation: bool = False
) -> GateApprovalRequest:
    if not isinstance(payload, dict):
        raise CommandAdapterError("invalid_request", "the JSON body must be an object")
    allowed = {
        "schema",
        "gate_id",
        "actor_id",
        "decision",
        "reason",
        "expected_state",
        "transition_target",
        "role_id",
        "evidence_references",
        "precondition_digest",
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
    for field in (
        "gate_id",
        "actor_id",
        "decision",
        "expected_state",
        "transition_target",
        "role_id",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CommandAdapterError("invalid_request", f"command field {field} is required")
        if value != value.strip():
            raise CommandAdapterError(
                "invalid_request", f"command field {field} must already be canonical"
            )
        values[field] = value
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise CommandAdapterError("invalid_request", "command field reason is required")
    if not _SLUG.fullmatch(values["gate_id"]):
        raise CommandAdapterError("invalid_request", "gate_id must be a safe Agora slug")
    if len(values["actor_id"]) > 256 or any(
        character in values["actor_id"] for character in ("/", "\\", "\x00", "\n", "\r")
    ):
        raise CommandAdapterError("invalid_request", "actor_id is invalid")
    if values["decision"] not in {"approved", "rejected"}:
        raise CommandAdapterError("invalid_request", "decision must be approved or rejected")
    if len(reason) > _MAX_REASON:
        raise CommandAdapterError("invalid_request", "reason is longer than 4000 characters")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in reason):
        raise CommandAdapterError("invalid_request", "reason contains unsupported control text")
    if not _SLUG.fullmatch(values["expected_state"]):
        raise CommandAdapterError("invalid_request", "expected_state must be a safe Agora slug")
    if not _SLUG.fullmatch(values["transition_target"]):
        raise CommandAdapterError("invalid_request", "transition_target must be a safe Agora slug")
    if not _SLUG.fullmatch(values["role_id"]):
        raise CommandAdapterError("invalid_request", "role_id must be a safe Agora slug")

    references = payload.get("evidence_references", [])
    if not isinstance(references, list) or len(references) > _MAX_REFERENCES:
        raise CommandAdapterError(
            "invalid_request", "evidence_references must be a bounded JSON array"
        )
    if any(
        not isinstance(reference, str)
        or not reference.strip()
        or len(reference) > _MAX_REFERENCE_LENGTH
        or any(ord(character) < 32 for character in reference)
        for reference in references
    ):
        raise CommandAdapterError("invalid_request", "evidence_references are invalid")

    precondition_digest = payload.get("precondition_digest")
    if precondition_digest is not None and (
        not isinstance(precondition_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", precondition_digest) is None
    ):
        raise CommandAdapterError(
            "invalid_request", "precondition_digest must be a lowercase SHA-256 value or null"
        )
    if for_confirmation and precondition_digest is None:
        raise CommandAdapterError(
            "command.stale-precondition",
            "gate confirmation requires the precondition digest issued by Core",
        )
    if not for_confirmation and precondition_digest is not None:
        raise CommandAdapterError(
            "invalid_request", "gate preparation must not include a precondition digest"
        )

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
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,31}", authentication["algorithm"]) is None:
            raise CommandAdapterError("invalid_request", "authentication algorithm is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", authentication["fingerprint"]) is None:
            raise CommandAdapterError(
                "invalid_request", "authentication fingerprint must be lowercase SHA-256"
            )
        if len(authentication["signature"]) > 8_192 or any(
            ord(character) < 32 for character in authentication["signature"]
        ):
            raise CommandAdapterError("invalid_request", "detached signature is invalid")

    return GateApprovalRequest(
        gate_id=values["gate_id"],
        actor_id=values["actor_id"],
        decision=values["decision"],
        reason=reason,
        expected_state=values["expected_state"],
        transition_target=values["transition_target"],
        role_id=values["role_id"],
        evidence_references=tuple(references),
        precondition_digest=precondition_digest,
        authentication=authentication,
    )


class CoreCommandGateway:
    """Invoke Agora Core application services without terminal-command indirection."""

    @staticmethod
    def _bindings() -> tuple[type[Exception], object, object]:
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

        return AgoraApplicationError, AgoraCommandService, ApproveGateCommand

    @staticmethod
    def _command(
        command_type: object,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
        *,
        include_authentication: bool,
    ) -> object:
        return command_type(  # type: ignore[operator]
            project_identity=selection.project,
            swarm_id=swarm_id,
            work_id=work_id,
            gate_id=request.gate_id,
            actor_id=request.actor_id,
            decision=request.decision,
            reason=request.reason,
            expected_state=request.expected_state,
            transition_target=request.transition_target,
            role_id=request.role_id,
            evidence_references=request.evidence_references,
            precondition_digest=request.precondition_digest,
            authentication=request.authentication if include_authentication else None,
        )

    @staticmethod
    def _dto(value: object, expected_schema: str) -> dict[str, object]:
        try:
            payload = value.to_dict()  # type: ignore[attr-defined]
        except (AttributeError, TypeError) as error:
            raise CommandAdapterError(
                "command.version-incompatible",
                f"Agora Core did not return {expected_schema}",
            ) from error
        if not isinstance(payload, dict) or payload.get("schema") != expected_schema:
            found = payload.get("schema") if isinstance(payload, dict) else None
            raise CommandAdapterError(
                "command.version-incompatible",
                f"Studio requires schema {expected_schema}; found {found!r}",
            )
        return payload

    @staticmethod
    def _require_string(payload: Mapping[str, object], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            raise CommandAdapterError(
                "core.schema-incompatible", f"Core response field {field} must be a string"
            )
        return value

    @staticmethod
    def _require_array(payload: Mapping[str, object], field: str) -> list[object]:
        value = payload.get(field)
        if not isinstance(value, list):
            raise CommandAdapterError(
                "core.schema-incompatible", f"Core response field {field} must be an array"
            )
        return value

    @staticmethod
    def _require_object(payload: Mapping[str, object], field: str) -> dict[str, object]:
        value = payload.get(field)
        if not isinstance(value, dict):
            raise CommandAdapterError(
                "core.schema-incompatible", f"Core response field {field} must be an object"
            )
        return value

    def _validate_identity(
        self,
        payload: Mapping[str, object],
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> None:
        expected = {
            "project_identity": selection.project,
            "swarm_id": swarm_id,
            "work_id": work_id,
            "gate_id": request.gate_id,
            "actor_id": request.actor_id,
            "role_id": request.role_id,
            "decision": request.decision,
        }
        for field, value in expected.items():
            if self._require_string(payload, field) != value:
                raise CommandAdapterError(
                    "core.schema-incompatible", f"Core response field {field} changed identity"
                )

    def prepare_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]:
        if request.authentication is not None:
            raise CommandAdapterError(
                "invalid_request", "gate preparation must not include authentication material"
            )
        if request.precondition_digest is not None:
            raise CommandAdapterError(
                "invalid_request", "gate preparation must not include a precondition digest"
            )
        application_error, service_type, command_type = self._bindings()
        command = self._command(
            command_type, selection, swarm_id, work_id, request, include_authentication=False
        )
        try:
            prepared = service_type.from_path(selection.path).prepare_gate_decision(command)  # type: ignore[attr-defined]
        except application_error as error:
            safe = error.to_dict()  # type: ignore[attr-defined]
            raise CommandAdapterError(str(safe["code"]), str(safe["message"])) from error
        except Exception as error:
            raise CommandAdapterError(
                "command.persistence-failed", "Agora Core could not prepare the gate decision"
            ) from error
        payload = self._dto(prepared, PREPARED_GATE_SCHEMA)
        self._validate_identity(payload, selection, swarm_id, work_id, request)
        for field in (
            "command_schema",
            "authorization_schema",
            "authorization_payload",
            "authorization_digest",
            "expected_state",
            "transition_target",
            "reason",
            "freshness",
        ):
            self._require_string(payload, field)
        if payload["command_schema"] != APPROVE_GATE_SCHEMA:
            raise CommandAdapterError(
                "command.version-incompatible", "Core prepared an incompatible gate command"
            )
        if payload["authorization_schema"] != AUTHORIZATION_SCHEMA:
            raise CommandAdapterError(
                "command.version-incompatible",
                "Core prepared an incompatible authorization payload",
            )
        expected = {
            "expected_state": request.expected_state,
            "transition_target": request.transition_target,
        }
        for field, value in expected.items():
            if payload[field] != value:
                raise CommandAdapterError(
                    "core.schema-incompatible", f"Core response field {field} changed the command"
                )
        evidence_references = self._require_array(payload, "evidence_references")
        if any(
            not isinstance(reference, str) or not reference for reference in evidence_references
        ):
            raise CommandAdapterError(
                "core.schema-incompatible",
                "Core response field evidence_references is invalid",
            )
        precondition_digest = self._require_string(payload, "precondition_digest")
        if re.fullmatch(r"[0-9a-f]{64}", precondition_digest) is None:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core response field precondition_digest is invalid"
            )
        if re.fullmatch(r"[0-9a-f]{64}", str(payload["authorization_digest"])) is None:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core response field authorization_digest is invalid"
            )
        authorization_payload = str(payload["authorization_payload"])
        try:
            authorization_bytes = authorization_payload.encode("ascii")
        except UnicodeEncodeError as error:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core authorization payload must be ASCII JSON"
            ) from error
        if (
            not authorization_payload.endswith("\n")
            or hashlib.sha256(authorization_bytes).hexdigest() != payload["authorization_digest"]
        ):
            raise CommandAdapterError(
                "core.schema-incompatible", "Core authorization payload digest does not match"
            )
        try:
            canonical = json.loads(authorization_payload)
        except (json.JSONDecodeError, TypeError) as error:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core authorization payload is not canonical JSON"
            ) from error
        canonical_expected = {
            "schema": APPROVE_GATE_SCHEMA,
            "authorization_schema": AUTHORIZATION_SCHEMA,
            "project_identity": selection.project,
            "swarm_id": swarm_id,
            "work_id": work_id,
            "gate_id": request.gate_id,
            "actor_id": request.actor_id,
            "decision": request.decision,
            "reason": payload["reason"],
            "expected_state": payload["expected_state"],
            "transition_target": payload["transition_target"],
            "role_id": request.role_id,
            "evidence_references": evidence_references,
            "precondition_digest": precondition_digest,
        }
        if canonical != canonical_expected:
            raise CommandAdapterError(
                "core.schema-incompatible",
                "Core authorization payload does not match the prepared command",
            )
        if not isinstance(payload.get("authentication_required"), bool):
            raise CommandAdapterError(
                "core.schema-incompatible",
                "Core response field authentication_required must be boolean",
            )
        for field in (
            "authentication_algorithm",
            "authentication_fingerprint",
            "authentication_public_key",
            "expires_at",
        ):
            if payload.get(field) is not None and not isinstance(payload[field], str):
                raise CommandAdapterError(
                    "core.schema-incompatible", f"Core response field {field} must be text or null"
                )
        fingerprint = payload.get("authentication_fingerprint")
        if fingerprint is not None and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
            raise CommandAdapterError(
                "core.schema-incompatible",
                "Core response field authentication_fingerprint is invalid",
            )
        if payload["freshness"] != "governed-material/v1":
            raise CommandAdapterError(
                "command.version-incompatible", "Core prepared an incompatible freshness contract"
            )
        if payload["authentication_required"] and (
            payload.get("authentication_algorithm") is None
            or payload.get("authentication_fingerprint") is None
            or payload.get("authentication_public_key") is None
        ):
            raise CommandAdapterError(
                "core.schema-incompatible", "Core omitted required authentication metadata"
            )
        return payload

    def approve_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]:
        if request.precondition_digest is None:
            raise CommandAdapterError(
                "command.stale-precondition",
                "gate confirmation requires the precondition digest issued by Core",
            )
        application_error, service_type, command_type = self._bindings()

        command = self._command(
            command_type, selection, swarm_id, work_id, request, include_authentication=True
        )
        try:
            projection = service_type.from_path(selection.path).approve_gate(command)  # type: ignore[attr-defined]
        except application_error as error:
            safe = error.to_dict()  # type: ignore[attr-defined]
            raise CommandAdapterError(str(safe["code"]), str(safe["message"])) from error
        except Exception as error:
            raise CommandAdapterError(
                "command.persistence-failed",
                "Agora Core could not complete the gate decision",
            ) from error
        payload = self._dto(projection, GATE_PROJECTION_SCHEMA)
        self._validate_identity(payload, selection, swarm_id, work_id, request)
        if self._require_string(payload, "reason") != request.reason:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core response field reason changed the command"
            )
        if self._require_string(payload, "precondition_digest") != request.precondition_digest:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core response field precondition_digest changed"
            )
        if self._require_array(payload, "evidence_references") != list(request.evidence_references):
            raise CommandAdapterError(
                "core.schema-incompatible", "Core response field evidence_references changed"
            )
        lifecycle = payload.get("lifecycle")
        activity = payload.get("activity")
        if not isinstance(lifecycle, dict) or lifecycle.get("schema") != LIFECYCLE_SCHEMA:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core returned an incompatible lifecycle projection"
            )
        if lifecycle.get("swarm_id") != swarm_id or lifecycle.get("work_id") != work_id:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core lifecycle projection changed command identity"
            )
        for field in (
            "method",
            "current_state",
            "operational_status",
            "terminal_state",
        ):
            self._require_string(lifecycle, field)
        for field in (
            "available_transitions",
            "satisfied_criteria",
            "required_artifacts",
            "artifact_kinds",
            "evidence_results",
            "approval_roles",
            "states",
            "transitions",
            "gates",
        ):
            self._require_array(lifecycle, field)
        self._require_object(lifecycle, "acceptance_criteria")
        self._require_object(lifecycle, "criterion_statuses")
        if not isinstance(activity, dict) or activity.get("schema") != ACTIVITY_SCHEMA:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core returned an incompatible Activity projection"
            )
        if activity.get("swarm_id") != swarm_id or activity.get("work_id") != work_id:
            raise CommandAdapterError(
                "core.schema-incompatible", "Core Activity projection changed command identity"
            )
        for field in ("timestamp", "type", "summary", "source"):
            self._require_string(activity, field)
        for field in ("actor", "session_id", "tool_run_id"):
            if activity.get(field) is not None and not isinstance(activity[field], str):
                raise CommandAdapterError(
                    "core.schema-incompatible", f"Core Activity field {field} must be text or null"
                )
        return payload
