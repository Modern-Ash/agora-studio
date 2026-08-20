from __future__ import annotations

from pathlib import Path

from agora_studio.core import ActivityQuery, CoreGatewayError


class FakeGateway:
    core_version = "0.7.0"

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.failure: CoreGatewayError | None = None

    def _record(self, *call: object) -> None:
        self.calls.append(call)
        if self.failure is not None:
            raise self.failure

    def project_overview(self, project: Path) -> dict[str, object]:
        self._record("project_overview", project)
        return {
            "schema": "agora/application/project-overview/v1",
            "project": project.name,
            "version": "0.3.0",
            "integration": "generic",
            "provider": "local",
            "model": "local",
            "default_method": "scrum",
            "max_delegation_depth": 3,
            "created_at": "2026-08-20T12:00:00Z",
            "branch": "main",
            "counts": {"actors": 1, "swarms": 1, "work": 1, "sessions": 1},
            "swarm_statuses": {"active": 1},
            "work_states": {"verifying": 1},
            "work_operational_statuses": {"active": 1},
            "delegation_statuses": {},
            "session_statuses": {"completed": 1},
            "tool_run_statuses": {},
            "attention": {
                "forming-swarms": [],
                "active-work": ["delivery/release"],
                "blocked-work": [],
                "open-delegations": [],
                "unfinished-sessions": [],
                "failed-sessions": [],
                "failed-tool-runs": [],
            },
        }

    def list_actors(self, project: Path) -> list[dict[str, object]]:
        self._record("list_actors", project)
        return [
            {
                "schema": "agora/application/actor-summary/v1",
                "id": "owner",
                "reference": "project:owner",
                "name": "Owner",
                "kind": "human",
                "capabilities": ["acceptance"],
                "integration": None,
                "provider": None,
                "model": None,
                "represented_swarm": None,
                "authentication_required": False,
                "authentication_fingerprint": None,
                "runtime_fallbacks": [],
                "authentication_algorithm": None,
                "authentication_public_key": None,
                "authentication_revoked_at": None,
                "authentication_revoked_reason": None,
            }
        ]

    def list_swarms(self, project: Path) -> list[dict[str, object]]:
        self._record("list_swarms", project)
        return [
            {
                "schema": "agora/application/swarm-summary/v1",
                "id": "delivery",
                "method": "scrum",
                "status": "active",
                "branch": "main",
                "objective": "Ship",
                "required_roles": ["product-owner"],
                "assignments": {"product-owner": "project:owner"},
                "work_states": ["verifying"],
            }
        ]

    def list_work_items(self, project: Path) -> list[dict[str, object]]:
        self._record("list_work_items", project)
        return [
            {
                "schema": "agora/application/work-item-summary/v1",
                "id": "release",
                "swarm_id": "delivery",
                "title": "Release",
                "description": "Ship safely",
                "state": "verifying",
                "operational_status": "active",
                "status_reason": None,
                "status_by": None,
                "status_at": None,
                "acceptance_criteria": {"accepted": "Release accepted"},
                "satisfied_criteria": ["accepted"],
                "criterion_statuses": {"accepted": ["accepted"]},
                "required_artifacts": ["test-report"],
                "artifact_kinds": ["test-report"],
                "evidence_results": ["success"],
                "approval_roles": [],
                "child_work_refs": [],
                "budget_limits": None,
                "delegation_id": None,
                "parent_work_ref": None,
            }
        ]

    def get_work_item(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        self._record("get_work_item", project, swarm, work)
        if (swarm, work) != ("delivery", "release"):
            raise CoreGatewayError("read.resource-not-found", "work item not found")
        return {
            **self.list_work_items(project)[0],
            "schema": "agora/application/work-item-detail/v2",
            "artifacts": self.artifacts(project, swarm, work),
            "evidence": self.evidence(project, swarm, work),
            "approvals": self.approvals(project, swarm, work),
        }

    def list_sessions(self, project: Path) -> list[dict[str, object]]:
        self._record("list_sessions", project)
        return [
            {
                "schema": "agora/application/session-summary/v1",
                "id": "session-1",
                "actor": "project:owner",
                "executor": "project:owner",
                "swarm_id": "delivery",
                "work_id": "release",
                "roles": ["product-owner"],
                "integration": "generic",
                "provider": "local",
                "model": "local",
                "status": "completed",
                "record_uri": "repo://session",
                "context_uri": "repo://context",
                "launch_command": [],
                "runtime_available": True,
                "created_at": "2026-08-20T12:00:00Z",
                "exit_code": 0,
                "timeout_seconds": 1,
                "max_output_bytes": 1,
                "output_bytes": 0,
                "termination_reason": None,
                "context_sha256": None,
                "authentication_verified": False,
                "authentication_fingerprint": None,
                "authentication_public_key": None,
                "authorization_sha256": None,
                "authorization_signature": None,
                "preparation_action_id": None,
            }
        ]

    def activity(self, project: Path, query: ActivityQuery) -> list[dict[str, object]]:
        self._record("activity", project, query)
        return [
            {
                "schema": "agora/application/activity-entry/v1",
                "timestamp": "2026-08-20T12:00:00Z",
                "type": "work.transitioned",
                "summary": "from=reviewing to=verifying",
                "actor": "project:owner",
                "swarm_id": "delivery",
                "work_id": "release",
                "session_id": None,
                "tool_run_id": None,
                "source": "repo://events",
            }
        ]

    def get_method(self, project: Path, swarm: str) -> dict[str, object]:
        self._record("get_method", project, swarm)
        return {
            "schema": "agora/application/method-summary/v1",
            "id": "scrum",
            "name": "Scrum",
            "version": "1.0.0",
            "required_roles": ["product-owner"],
            "states": [
                {
                    "schema": "agora/application/method-state-summary/v1",
                    "id": "verifying",
                    "initial": False,
                    "terminal": False,
                },
                {
                    "schema": "agora/application/method-state-summary/v1",
                    "id": "completed",
                    "initial": False,
                    "terminal": True,
                },
            ],
            "transitions": [],
            "gates": [],
            "wip_limits": {},
            "criterion_stages": [],
            "criterion_stage_roles": {},
        }

    def lifecycle(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        self._record("lifecycle", project, swarm, work)
        return {
            "schema": "agora/application/lifecycle-projection/v2",
            "swarm_id": swarm,
            "work_id": work,
            "method": "scrum",
            "current_state": "verifying",
            "operational_status": "active",
            "terminal_state": "completed",
            "available_transitions": ["completed"],
            "acceptance_criteria": {"accepted": "Release accepted"},
            "satisfied_criteria": ["accepted"],
            "criterion_statuses": {"accepted": ["accepted"]},
            "required_artifacts": ["test-report"],
            "artifact_kinds": ["test-report"],
            "evidence_results": ["success"],
            "approval_roles": [],
            "states": self.get_method(project, swarm)["states"],
            "transitions": [
                {
                    "schema": "agora/application/transition-summary/v1",
                    "source": "verifying",
                    "target": "completed",
                    "authorized_roles": ["product-owner"],
                    "gate_id": "completion",
                    "required_approval_roles": ["product-owner"],
                    "available": False,
                    "blockers": [
                        {
                            "schema": "agora/application/gate-blocker-summary/v1",
                            "code": "gate.approvals-missing",
                            "category": "approval",
                            "message": "Required approval roles are missing",
                            "references": ["product-owner"],
                        }
                    ],
                }
            ],
            "gates": [],
        }

    def artifacts(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]:
        self._record("artifacts", project, swarm, work)
        return [
            {
                "schema": "agora/application/artifact-summary/v2",
                "kind": "test-report",
                "uri": "repo://report",
                "produced_by": "project:owner",
                "timestamp": "2026-08-20T12:00:00Z",
                "activity": None,
            }
        ]

    def evidence(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]:
        self._record("evidence", project, swarm, work)
        return [
            {
                "schema": "agora/application/evidence-summary/v2",
                "type": "test-run",
                "result": "success",
                "artifact_references": ["repo://report"],
                "produced_by": "project:owner",
                "timestamp": "2026-08-20T12:00:00Z",
                "activity": None,
            }
        ]

    def approvals(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]:
        self._record("approvals", project, swarm, work)
        return []

    def traceability(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        self._record("traceability", project, swarm, work)
        return {
            "schema": "agora/application/traceability-summary/v1",
            "swarm_id": swarm,
            "work_id": work,
            "state": "verifying",
            "stale": False,
            "criteria": [],
            "clarifications": {},
            "gherkin": [],
            "consistency": [],
            "artifacts": self.artifacts(project, swarm, work),
            "evidence": self.evidence(project, swarm, work),
            "activity": [],
        }

    def specification(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        self._record("specification", project, swarm, work)
        return {
            "schema": "agora/application/specification-summary/v1",
            "available": False,
            "uri": None,
            "revisions": [],
            "has_history": False,
            "working_tree": False,
            "truncated": False,
            "reason": "no specification registered",
        }

    def specification_revision(
        self, project: Path, swarm: str, work: str, revision: str
    ) -> dict[str, object]:
        self._record("specification_revision", project, swarm, work, revision)
        return {
            "schema": "agora/application/specification-revision-detail/v1",
            "available": revision == "working-tree",
            "uri": "repo://docs/spec.md",
            "revision_id": revision,
            "kind": "working-tree" if revision == "working-tree" else None,
            "sha": None,
            "previous_revision_id": None,
            "timestamp": None,
            "author": None,
            "subject": "Modified, uncommitted specification",
            "content": "# Specification\n" if revision == "working-tree" else None,
            "diff": "+# Specification\n" if revision == "working-tree" else None,
            "size_bytes": 16 if revision == "working-tree" else 0,
            "content_truncated": False,
            "diff_truncated": False,
            "encoding": "utf-8" if revision == "working-tree" else "unavailable",
            "binary": False,
            "reason": None if revision == "working-tree" else "revision unavailable",
        }

    def gate_options(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        self._record("gate_options", project, swarm, work)
        common = {
            "schema": "agora/application/gate-decision-option-summary/v2",
            "swarm_id": swarm,
            "work_id": work,
            "expected_state": "verifying",
            "transition_source": "verifying",
            "transition_target": "completed",
            "gate_id": "completion",
            "role_id": "product-owner",
            "actor_id": "project:owner",
            "allowed": True,
            "blockers": [],
            "required_evidence_types": ["test-run"],
            "evidence_references": ["repo://report"],
            "evidence_references_by_type": {"test-run": ["repo://report"]},
            "authentication_required": False,
            "authentication_algorithm": None,
            "authentication_fingerprint": None,
            "unavailable_reason": None,
        }
        return {
            "schema": "agora/application/gate-decision-options-projection/v2",
            "swarm_id": swarm,
            "work_id": work,
            "current_state": "verifying",
            "operational_status": "active",
            "terminal": False,
            "reason": None,
            "options": [
                {**common, "decision": "approved", "evidence_required": True},
                {
                    **common,
                    "decision": "rejected",
                    "evidence_required": False,
                    "required_evidence_types": [],
                    "evidence_references_by_type": {},
                },
            ],
        }

    def work_control(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        self._record("work_control", project, swarm, work)
        detail = self.get_work_item(project, swarm, work)
        return {
            "schema": "agora/application/work-control-projection/v2",
            "snapshot_token": "a" * 64,
            "work": detail,
            "lifecycle": self.lifecycle(project, swarm, work),
            "artifacts": detail["artifacts"],
            "evidence": detail["evidence"],
            "approvals": detail["approvals"],
            "traceability": self.traceability(project, swarm, work),
            "specification_history": self.specification(project, swarm, work),
            "gate_decision_options": self.gate_options(project, swarm, work),
        }
