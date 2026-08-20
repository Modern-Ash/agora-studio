from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
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

from agora_studio.server import create_server


def create_gate_project(root: Path) -> Path:
    project = root / "governed-project"
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
        "schema": "agora/application/approve-gate-command/v1",
        "gate_id": "completion",
        "actor_id": "owner",
        "decision": decision,
        "reason": f"Integration test {decision}",
        "expected_state": expected_state,
        "evidence_references": ["repo://reports/release.txt"],
    }


class RealCoreStudioIntegrationTests(unittest.TestCase):
    def test_real_read_approval_persistence_activity_and_refresh(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"AGORA_HOME": str(Path(directory) / "home")}),
        ):
            project = create_gate_project(Path(directory))
            studio = RunningStudio()
            try:
                status, opened = studio.request(
                    "POST", "/api/v1/projects/select", {"path": str(project)}
                )
                self.assertEqual(status, 200)
                self.assertEqual(opened["project"]["core_version"], "0.5.0")

                for route in (
                    "/api/v1/overview",
                    "/api/v1/lifecycle?swarm=delivery&work=release",
                    "/api/v1/artifacts?swarm=delivery&work=release",
                ):
                    status, payload = studio.request("GET", route)
                    self.assertEqual(status, 200, payload)

                status, stale = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    gate_payload(expected_state="implementing"),
                )
                self.assertEqual((status, stale["error"]), (409, "command.stale-precondition"))

                status, decision = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    gate_payload(),
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
                    gate_payload(),
                )
                self.assertEqual(
                    (status, duplicate["error"]), (409, "command.gate-already-resolved")
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
                status, decision = studio.request(
                    "POST",
                    "/api/v1/work-items/delivery/release/approvals",
                    gate_payload("rejected"),
                )
                self.assertEqual(status, 200, decision)
                self.assertEqual(decision["projection"]["decision"], "rejected")
                _, activity = studio.request("GET", "/api/v1/activity?limit=500")
                self.assertIn("gate.rejected", [item["type"] for item in activity["events"]])
            finally:
                studio.close()


if __name__ == "__main__":
    unittest.main()
