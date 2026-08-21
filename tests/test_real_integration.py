from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import subprocess
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agora.model import (
    AddActorInput,
    AddArtifactInput,
    AddEvidenceInput,
    AssignActorInput,
    CreateSwarmInput,
    CreateWorkInput,
    InitInput,
    TransitionWorkInput,
    WorkActorInput,
)
from agora.workspace import AgoraWorkspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agora_studio.server import create_server


def create_gate_project(
    root: Path,
    *,
    include_evidence: bool = True,
    owner_public_key: Path | None = None,
    name: str = "governed-project",
) -> Path:
    project = root / name
    project.mkdir()
    workspace = AgoraWorkspace(cwd=project)
    workspace.initialize(InitInput(integration="generic", default_method="scrum"))
    for actor in (
        AddActorInput(
            id="owner",
            name="Owner",
            kind="human",
            capabilities=["backlog-management", "acceptance"],
            scope="project",
            public_key=str(owner_public_key) if owner_public_key else None,
            require_authentication=owner_public_key is not None,
        ),
        AddActorInput(
            id="facilitator",
            name="Facilitator",
            kind="ai-agent",
            capabilities=["facilitation", "governance"],
            scope="project",
        ),
        AddActorInput(
            id="developer",
            name="Developer",
            kind="ai-agent",
            capabilities=["implementation"],
            scope="project",
        ),
    ):
        workspace.add_actor(actor)
    workspace.create_swarm(
        CreateSwarmInput(id="delivery", objective="Deliver safely", create_branch=False)
    )
    for role, actor in (
        ("product-owner", "owner"),
        ("scrum-master", "facilitator"),
        ("developer", "developer"),
    ):
        workspace.assign_actor(AssignActorInput(swarm_id="delivery", role_id=role, actor_id=actor))
    workspace.create_work(
        CreateWorkInput(
            swarm_id="delivery",
            id="release",
            title="Release safely",
            actor_id="owner",
            acceptance_criteria=[("accepted", "The release is accepted")],
            required_artifacts=["test-report"],
        )
    )
    for state, actor in (
        ("planned", "developer"),
        ("implementing", "developer"),
        ("reviewing", "developer"),
        ("verifying", "facilitator"),
    ):
        workspace.transition_work(
            TransitionWorkInput(
                swarm_id="delivery", work_id="release", actor_id=actor, target_state=state
            )
        )
    for stage, actor in (
        ("specified", "owner"),
        ("implemented", "developer"),
        ("verified", "facilitator"),
        ("accepted", "owner"),
    ):
        workspace.satisfy_criterion(
            WorkActorInput(swarm_id="delivery", work_id="release", actor_id=actor),
            "accepted",
            stage,
        )
    report = project / "reports" / "release.txt"
    report.parent.mkdir()
    report.write_text("passed\n", encoding="utf-8")
    workspace.add_artifact(
        AddArtifactInput(
            swarm_id="delivery",
            work_id="release",
            actor_id="developer",
            kind="test-report",
            uri="repo://reports/release.txt",
        )
    )
    if include_evidence:
        workspace.add_evidence(
            AddEvidenceInput(
                swarm_id="delivery",
                work_id="release",
                actor_id="developer",
                type="test-run",
                result="success",
                artifact_refs=["repo://reports/release.txt"],
            )
        )
    return project


def add_multiple_gate_options(project: Path) -> None:
    method = project / ".agora" / "methods" / "scrum"
    completion = method / "gates" / "completion.md"
    completion.write_text(
        completion.read_text(encoding="utf-8").replace(
            'required-approval-roles: ["product-owner"]',
            'required-approval-roles: ["product-owner","scrum-master"]',
        ),
        encoding="utf-8",
    )
    (method / "gates" / "rework-review.md").write_text(
        """---
schema: "agora/gate/v1"
id: "rework-review"
require-all-criteria: false
require-required-artifacts: false
require-successful-evidence: false
required-approval-roles: ["scrum-master"]
---

# Rework review gate
""",
        encoding="utf-8",
    )
    (method / "transitions" / "08-verifying-reviewing.md").write_text(
        """---
schema: "agora/transition/v1"
from: "verifying"
to: "reviewing"
roles: ["scrum-master"]
gate: "rework-review"
---

# Return to review
""",
        encoding="utf-8",
    )


class RunningStudio:
    def __init__(self) -> None:
        self.server = create_server(0, csrf_token="integration-token")
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method: str, path: str, payload: object | None = None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Host": f"127.0.0.1:{self.port}"}
        if method == "POST":
            headers.update(
                {
                    "Origin": f"http://127.0.0.1:{self.port}",
                    "X-Agora-Studio-CSRF": "integration-token",
                    "Content-Type": "application/json",
                }
            )
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result


def gate_payload(
    decision: str = "approved", expected_state: str = "verifying"
) -> dict[str, object]:
    return {
        "schema": "agora/application/approve-gate-command/v4",
        "gate_id": "completion",
        "actor_id": "project:owner",
        "decision": decision,
        "reason": f"Integration test {decision}",
        "expected_state": expected_state,
        "transition_target": "completed",
        "role_id": "product-owner",
        "evidence_references": ["repo://reports/release.txt"],
        "precondition_digest": None,
    }


def confirmation_payload(
    prepared: dict[str, object], authentication: dict[str, str] | None = None
) -> dict[str, object]:
    return {
        "schema": prepared["command_schema"],
        "gate_id": prepared["gate_id"],
        "actor_id": prepared["actor_id"],
        "decision": prepared["decision"],
        "reason": prepared["reason"],
        "expected_state": prepared["expected_state"],
        "transition_target": prepared["transition_target"],
        "role_id": prepared["role_id"],
        "evidence_references": prepared["evidence_references"],
        "evidence_content_sha256": prepared["evidence_content_sha256"],
        "actor_fingerprint": prepared.get("actor_fingerprint"),
        "precondition_digest": prepared["precondition_digest"],
        "prepared_at": prepared["prepared_at"],
        "expires_at": prepared.get("expires_at"),
        "authentication": authentication,
    }


class RealCoreStudioIntegrationTests(unittest.TestCase):
    def test_real_specification_history_and_revision_detail_stay_core_backed(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AGORA_HOME": str(Path(directory) / "home")}),
        ):
            project = create_gate_project(Path(directory))
            specification = project / "docs" / "spec.md"
            specification.parent.mkdir()
            specification.write_text("# Release specification\n", encoding="utf-8")
            workspace = AgoraWorkspace(cwd=project)
            workspace.add_artifact(
                AddArtifactInput(
                    swarm_id="delivery",
                    work_id="release",
                    actor_id="developer",
                    kind="spec",
                    uri="repo://docs/spec.md",
                )
            )
            for command in (
                ["git", "init"],
                ["git", "config", "user.name", "Studio Test"],
                ["git", "config", "user.email", "studio@example.invalid"],
                ["git", "add", "."],
                ["git", "commit", "-m", "docs: add release specification"],
            ):
                subprocess.run(command, cwd=project, check=True, capture_output=True)
            specification.write_text(
                "# Release specification\n\nWorking tree change.\n"
                + "".join(f"Requirement {index}\n" for index in range(2_100)),
                encoding="utf-8",
            )

            studio = RunningStudio()
            try:
                self.assertEqual(
                    studio.request("POST", "/api/v1/projects/select", {"path": str(project)})[0],
                    200,
                )
                status, history = studio.request(
                    "GET", "/api/v1/specification-history?swarm=delivery&work=release"
                )
                self.assertEqual(status, 200, history)
                self.assertTrue(history["specification"]["working_tree"])
                revision_id = history["specification"]["revisions"][0]["id"]
                status, detail = studio.request(
                    "GET",
                    f"/api/v1/specification-revisions/{revision_id}?swarm=delivery&work=release",
                )
                self.assertEqual(status, 200, detail)
                self.assertEqual(detail["revision"]["kind"], "working-tree")
                self.assertIn("Working tree change", detail["revision"]["content"])
                self.assertIn("Working tree change", detail["revision"]["diff"])
                self.assertTrue(detail["revision"]["content_truncated"])
                self.assertTrue(detail["revision"]["diff_truncated"])

                status, unavailable = studio.request(
                    "GET",
                    "/api/v1/specification-revisions/" + "0" * 40 + "?swarm=delivery&work=release",
                )
                self.assertEqual(status, 200, unavailable)
                self.assertFalse(unavailable["revision"]["available"])
                self.assertIn("not present", unavailable["revision"]["reason"])
            finally:
                studio.close()

    def test_real_read_approval_persistence_activity_and_refresh(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AGORA_HOME": str(Path(directory) / "home")}),
        ):
            project = create_gate_project(Path(directory))
            add_multiple_gate_options(project)
            studio = RunningStudio()
            try:
                status, opened = studio.request(
                    "POST", "/api/v1/projects/select", {"path": str(project)}
                )
                self.assertEqual(status, 200)
                self.assertEqual(opened["project"]["core_version"], "0.8.0")

                responses = {}
                for route in (
                    "/api/v1/overview",
                    "/api/v1/work-items/delivery/release",
                    "/api/v1/lifecycle?swarm=delivery&work=release",
                    "/api/v1/artifacts?swarm=delivery&work=release",
                ):
                    status, payload = studio.request("GET", route)
                    self.assertEqual(status, 200, payload)
                    responses[route] = payload

                options = responses["/api/v1/work-items/delivery/release"]["control"][
                    "gate_decision_options"
                ]["options"]
                self.assertEqual(len(options), 6)
                self.assertEqual(
                    {item["transition_target"] for item in options},
                    {"completed", "reviewing"},
                )
                self.assertEqual(
                    {item["role_id"] for item in options},
                    {"product-owner", "scrum-master"},
                )

                status, prepared = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals/prepare",
                    gate_payload(),
                )
                self.assertEqual(status, 200, prepared)
                self.assertFalse(prepared["preparation"]["authentication_required"])
                self.assertEqual(
                    prepared["preparation"]["command_schema"],
                    "agora/application/approve-gate-command/v4",
                )
                self.assertRegex(prepared["preparation"]["precondition_digest"], r"^[0-9a-f]{64}$")

                status, stale = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    {
                        **confirmation_payload(prepared["preparation"]),
                        "precondition_digest": "0" * 64,
                    },
                )
                self.assertEqual(status, 409)
                self.assertIn(
                    stale["error"],
                    ("command.stale-precondition", "command.governed-material-stale"),
                )

                status, decision = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    confirmation_payload(prepared["preparation"]),
                )
                self.assertEqual(status, 200, decision)
                self.assertEqual(decision["projection"]["decision"], "approved")

                status, activity = studio.request("GET", "/api/v1/activity?limit=500")
                self.assertEqual(status, 200)
                self.assertIn("approval.added", [item["type"] for item in activity["events"]])
                status, refreshed = studio.request(
                    "GET", "/api/v1/artifacts?swarm=delivery&work=release"
                )
                self.assertEqual(status, 200)
                self.assertEqual(refreshed["approvals"]["records"][0]["role"], "product-owner")

                status, duplicate = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    confirmation_payload(prepared["preparation"]),
                )
                self.assertEqual(status, 409)
                self.assertIn(
                    duplicate["error"],
                    ("command.stale-precondition", "command.governed-material-stale"),
                )
                status, resolved = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals/prepare",
                    gate_payload(),
                )
                self.assertEqual(
                    (status, resolved["error"]), (409, "command.gate-already-resolved")
                )
            finally:
                studio.close()

    def test_real_rejection_is_durable_and_visible_in_activity(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AGORA_HOME": str(Path(directory) / "home")}),
        ):
            project = create_gate_project(Path(directory))
            studio = RunningStudio()
            try:
                self.assertEqual(
                    studio.request("POST", "/api/v1/projects/select", {"path": str(project)})[0],
                    200,
                )
                status, prepared_response = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals/prepare",
                    gate_payload("rejected"),
                )
                self.assertEqual(status, 200, prepared_response)
                status, decision = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    confirmation_payload(prepared_response["preparation"]),
                )
                self.assertEqual(status, 200, decision)
                self.assertEqual(decision["projection"]["decision"], "rejected")
                _, activity = studio.request("GET", "/api/v1/activity?limit=500")
                self.assertIn("gate.rejected", [item["type"] for item in activity["events"]])
            finally:
                studio.close()

    def test_real_signed_actor_prepares_and_persists_a_detached_signature(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AGORA_HOME": str(Path(directory) / "home")}),
        ):
            root = Path(directory)
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            fingerprint = hashlib.sha256(public_key).hexdigest()
            project = create_gate_project(root)
            find_actor = AgoraWorkspace._find_actor

            def authenticated_owner(workspace, project_root, actor_id):
                actor = find_actor(workspace, project_root, actor_id)
                if actor.reference != "project:owner":
                    return actor
                return replace(
                    actor,
                    authentication_required=True,
                    authentication_algorithm="ed25519",
                    authentication_public_key=base64.b64encode(public_key).decode("ascii"),
                    authentication_fingerprint=fingerprint,
                )

            with (
                patch.object(AgoraWorkspace, "_find_actor", authenticated_owner),
                patch.object(AgoraWorkspace, "_assert_current_actor_key", lambda *args: None),
            ):
                studio = RunningStudio()
                try:
                    self.assertEqual(
                        studio.request("POST", "/api/v1/projects/select", {"path": str(project)})[
                            0
                        ],
                        200,
                    )
                    unsigned = gate_payload()
                    status, prepared_response = studio.request(
                        "POST",
                        "/api/v1/work-items/delivery/release/approvals/prepare",
                        unsigned,
                    )
                    self.assertEqual(status, 200, prepared_response)
                    prepared = prepared_response["preparation"]
                    self.assertTrue(prepared["authentication_required"])
                    signature = base64.b64encode(
                        private_key.sign(prepared["authorization_payload"].encode("ascii"))
                    ).decode("ascii")
                    signed = confirmation_payload(
                        prepared,
                        {
                            "algorithm": prepared["authentication_algorithm"],
                            "fingerprint": prepared["authentication_fingerprint"],
                            "signature": signature,
                        },
                    )
                    status, decision = studio.request(
                        "POST", "/api/v1/work-items/delivery/release/approvals", signed
                    )
                    self.assertEqual(status, 200, decision)
                    self.assertEqual(decision["projection"]["decision"], "approved")
                finally:
                    studio.close()


if __name__ == "__main__":
    unittest.main()
