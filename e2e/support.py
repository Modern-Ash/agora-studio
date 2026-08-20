from __future__ import annotations

import subprocess
import threading
from pathlib import Path

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


def create_gate_project(
    root: Path, *, include_evidence: bool = True, name: str = "governed-project"
) -> Path:
    project = root / name
    project.mkdir()
    workspace = AgoraWorkspace(cwd=project)
    workspace.initialize(InitInput(integration="generic", default_method="scrum"))
    actors = (
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
    )
    for actor in actors:
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
    """Install an alternate test-only Method Pack before Studio opens the project."""
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


def add_specification_history(project: Path) -> None:
    """Create two real Git revisions for the Core-backed specification browser."""

    specification = project / "docs" / "release.md"
    specification.parent.mkdir()
    specification.write_text("# Release\n\nFirst governed revision.\n", encoding="utf-8")
    AgoraWorkspace(cwd=project).add_artifact(
        AddArtifactInput(
            swarm_id="delivery",
            work_id="release",
            actor_id="developer",
            kind="spec",
            uri="repo://docs/release.md",
        )
    )
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Agora Studio E2E",
            "-c",
            "user.email=studio-e2e@example.invalid",
            "commit",
            "-m",
            "docs: register release specification",
        ],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    specification.write_text("# Release\n\nSecond governed revision.\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "docs/release.md"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Agora Studio E2E",
            "-c",
            "user.email=studio-e2e@example.invalid",
            "commit",
            "-m",
            "docs: revise release specification",
        ],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )


class RunningStudio:
    def __init__(self) -> None:
        self.server = create_server(0, csrf_token="e2e-token")
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
