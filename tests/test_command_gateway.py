from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agora_studio.commands import (
    CommandAdapterError,
    CoreCommandGateway,
    GateApprovalRequest,
    normalize_gate_approval,
)
from agora_studio.core import ProjectSelection


class FakeApplicationError(Exception):
    def to_dict(self):
        return {"code": "command.stale-precondition", "message": str(self)}


class FakeCommand:
    def __init__(self, **values):
        self.__dict__.update(values)


class FakeDTO:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return self.payload


class FakeService:
    prepared = None
    projection = None
    command = None

    def prepare_gate_decision(self, command):
        self.command = command
        type(self).command = command
        return self.prepared

    def approve_gate(self, command):
        return self.projection


class FakeServiceType:
    @classmethod
    def from_path(cls, path):
        return FakeService()


def request(authentication=None, precondition_digest=None) -> GateApprovalRequest:
    return GateApprovalRequest(
        gate_id="completion",
        actor_id="project:owner",
        decision="approved",
        reason="Evidence reviewed",
        expected_state="verifying",
        transition_target="completed",
        role_id="product-owner",
        evidence_references=("repo://report",),
        evidence_content_sha256={"repo://report": "c" * 64} if precondition_digest else None,
        actor_fingerprint=None,
        prepared_at="2026-08-20T12:00:00Z" if precondition_digest else None,
        expires_at=None,
        precondition_digest=precondition_digest,
        authentication=authentication,
    )


def valid_projection() -> dict[str, object]:
    return {
        "schema": "agora/application/gate-decision-projection/v3",
        "project_identity": "demo",
        "swarm_id": "delivery",
        "work_id": "release",
        "gate_id": "completion",
        "actor_id": "project:owner",
        "role_id": "product-owner",
        "decision": "approved",
        "reason": "Evidence reviewed",
        "evidence_references": ["repo://report"],
        "evidence_content_sha256": {"repo://report": "c" * 64},
        "actor_fingerprint": None,
        "precondition_digest": "b" * 64,
        "prepared_at": "2026-08-20T12:00:00Z",
        "expires_at": None,
        "lifecycle": {
            "schema": "agora/application/lifecycle-projection/v3",
            "swarm_id": "delivery",
            "work_id": "release",
            "method": "scrum",
            "current_state": "completed",
            "operational_status": "active",
            "terminal_state": "completed",
            "available_transitions": [],
            "acceptance_criteria": {},
            "satisfied_criteria": [],
            "criterion_statuses": {},
            "required_artifacts": [],
            "artifact_kinds": [],
            "evidence_results": [],
            "approval_roles": ["product-owner"],
            "states": [],
            "transitions": [],
            "gates": [],
        },
        "activity": {
            "schema": "agora/application/activity-entry/v1",
            "timestamp": "2026-08-20T12:00:00Z",
            "type": "gate.approved",
            "summary": "gate=completion decision=approved",
            "actor": "project:owner",
            "swarm_id": "delivery",
            "work_id": "release",
            "session_id": None,
            "tool_run_id": None,
            "source": "repo://events",
        },
    }


def valid_preparation() -> dict[str, object]:
    canonical = {
        "schema": "agora/application/approve-gate-command/v4",
        "authorization_schema": "agora/application/approve-gate-authorization/v4",
        "project_identity": "demo",
        "swarm_id": "delivery",
        "work_id": "release",
        "gate_id": "completion",
        "actor_id": "project:owner",
        "decision": "approved",
        "reason": "Evidence reviewed",
        "expected_state": "verifying",
        "transition_target": "completed",
        "role_id": "product-owner",
        "evidence_references": ["repo://report"],
        "evidence_content_sha256": {"repo://report": "c" * 64},
        "precondition_digest": "b" * 64,
        "prepared_at": "2026-08-20T12:00:00Z",
        "expires_at": None,
    }
    authorization_payload = (
        json.dumps(canonical, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    )
    return {
        "schema": "agora/application/prepared-gate-decision/v3",
        "command_schema": "agora/application/approve-gate-command/v4",
        "authorization_schema": "agora/application/approve-gate-authorization/v4",
        "authorization_payload": authorization_payload,
        "authorization_digest": hashlib.sha256(authorization_payload.encode("ascii")).hexdigest(),
        "precondition_digest": "b" * 64,
        "project_identity": "demo",
        "swarm_id": "delivery",
        "work_id": "release",
        "expected_state": "verifying",
        "transition_target": "completed",
        "gate_id": "completion",
        "decision": "approved",
        "actor_id": "project:owner",
        "role_id": "product-owner",
        "reason": "Evidence reviewed",
        "evidence_references": ["repo://report"],
        "evidence_content_sha256": {"repo://report": "c" * 64},
        "actor_fingerprint": None,
        "prepared_at": "2026-08-20T12:00:00Z",
        "expires_at": None,
        "authentication_required": True,
        "authentication_algorithm": "ed25519",
        "authentication_fingerprint": "a" * 64,
        "authentication_public_key": "public",
        "freshness": "governed-material/v2",
    }


class CommandGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = ProjectSelection(Path("/tmp/demo"), "demo", "0.8.0")
        self.gateway = CoreCommandGateway()
        self.bindings = patch.object(
            CoreCommandGateway,
            "_bindings",
            return_value=(FakeApplicationError, FakeServiceType, FakeCommand),
        )
        self.bindings.start()

    def tearDown(self) -> None:
        self.bindings.stop()

    def test_prepares_and_validates_the_exact_core_contract(self) -> None:
        FakeService.prepared = FakeDTO(valid_preparation())
        payload = self.gateway.prepare_gate(self.selection, "delivery", "release", request())
        self.assertTrue(payload["authentication_required"])
        self.assertEqual(payload["precondition_digest"], "b" * 64)

        malformed = {
            "changed expected state": ("expected_state", "reviewing", "core.schema-incompatible"),
            "future authorization": (
                "authorization_schema",
                "agora/application/approve-gate-authorization/v99",
                "command.version-incompatible",
            ),
            "invalid digest": ("authorization_digest", "not-a-digest", "core.schema-incompatible"),
            "invalid fingerprint": (
                "authentication_fingerprint",
                "not-a-fingerprint",
                "core.schema-incompatible",
            ),
        }
        for label, (field, value, code) in malformed.items():
            with self.subTest(label=label):
                preparation = valid_preparation()
                preparation[field] = value
                FakeService.prepared = FakeDTO(preparation)
                with self.assertRaises(CommandAdapterError) as captured:
                    self.gateway.prepare_gate(self.selection, "delivery", "release", request())
                self.assertEqual(captured.exception.code, code)

    def test_preserves_intent_text_and_accepts_core_canonical_values(self) -> None:
        FakeService.prepared = FakeDTO(valid_preparation())
        intent = replace(
            request(),
            reason="  Evidence\n reviewed  ",
            evidence_references=(" repo://report ", "repo://report"),
        )

        payload = self.gateway.prepare_gate(self.selection, "delivery", "release", intent)

        self.assertEqual(FakeService.command.reason, intent.reason)
        self.assertEqual(FakeService.command.evidence_references, intent.evidence_references)
        self.assertEqual(payload["reason"], "Evidence reviewed")
        self.assertEqual(payload["evidence_references"], ["repo://report"])

    def test_validates_the_complete_gate_decision_projection(self) -> None:
        FakeService.projection = FakeDTO(valid_projection())
        payload = self.gateway.approve_gate(
            self.selection,
            "delivery",
            "release",
            request(
                {
                    "algorithm": "ed25519",
                    "fingerprint": "a" * 64,
                    "signature": "signed",
                },
                "b" * 64,
            ),
        )
        self.assertEqual(payload["decision"], "approved")
        self.assertEqual(payload["activity"]["schema"], "agora/application/activity-entry/v1")

    def test_rejects_missing_future_and_malformed_projection_fields(self) -> None:
        cases = []
        payload = valid_projection()
        payload["schema"] = None
        cases.append((payload, "command.version-incompatible"))
        payload = valid_projection()
        payload["schema"] = "agora/application/gate-decision-projection/v99"
        cases.append((payload, "command.version-incompatible"))
        lifecycle = valid_projection()
        lifecycle["lifecycle"] = {"schema": "agora/application/lifecycle-projection/v99"}
        cases.append((lifecycle, "core.schema-incompatible"))
        activity = valid_projection()
        activity["activity"] = {"schema": "agora/application/activity-entry/v99"}
        cases.append((activity, "core.schema-incompatible"))
        missing = valid_projection()
        missing.pop("role_id")
        cases.append((missing, "core.schema-incompatible"))
        wrong_type = valid_projection()
        wrong_type["actor_id"] = ["project:owner"]
        cases.append((wrong_type, "core.schema-incompatible"))
        lifecycle_type = valid_projection()
        lifecycle_type["lifecycle"]["states"] = {}
        cases.append((lifecycle_type, "core.schema-incompatible"))
        activity_type = valid_projection()
        activity_type["activity"]["timestamp"] = None
        cases.append((activity_type, "core.schema-incompatible"))
        changed_reason = valid_projection()
        changed_reason["reason"] = "Different reason"
        cases.append((changed_reason, "core.schema-incompatible"))

        for payload, code in cases:
            with self.subTest(payload=payload):
                FakeService.projection = FakeDTO(payload)
                with self.assertRaises(CommandAdapterError) as captured:
                    self.gateway.approve_gate(
                        self.selection,
                        "delivery",
                        "release",
                        request(precondition_digest="b" * 64),
                    )
                self.assertEqual(captured.exception.code, code)

        FakeService.projection = object()
        with self.assertRaises(CommandAdapterError) as captured:
            self.gateway.approve_gate(
                self.selection,
                "delivery",
                "release",
                request(precondition_digest="b" * 64),
            )
        self.assertEqual(captured.exception.code, "command.version-incompatible")

    def test_http_shape_validation_rejects_missing_or_invalid_signatures(self) -> None:
        base = {
            "schema": "agora/application/approve-gate-command/v4",
            "gate_id": "completion",
            "actor_id": "project:owner",
            "decision": "approved",
            "reason": "Reviewed",
            "expected_state": "verifying",
            "transition_target": "completed",
            "role_id": "product-owner",
            "evidence_references": [],
            "precondition_digest": None,
        }
        self.assertIsNone(normalize_gate_approval(base).authentication)
        for authentication in (
            {"algorithm": "ed25519"},
            {"algorithm": "ed25519\n", "fingerprint": "a" * 64, "signature": "signed"},
            {"algorithm": "ed25519", "fingerprint": "bad", "signature": "signed"},
            {"algorithm": "ed25519", "fingerprint": "a" * 64, "signature": "\n"},
        ):
            with self.subTest(authentication=authentication):
                with self.assertRaises(CommandAdapterError):
                    normalize_gate_approval({**base, "authentication": authentication})


if __name__ == "__main__":
    unittest.main()
