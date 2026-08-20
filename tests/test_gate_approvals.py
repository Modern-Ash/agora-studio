from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from agora_studio.commands import CommandAdapterError, GateApprovalRequest
from agora_studio.core import ProjectSelection, ProjectStore
from agora_studio.server import handle_api


class RecordingCommands:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.calls: list[tuple[ProjectSelection, str, str, GateApprovalRequest]] = []

    def approve_gate(
        self,
        selection: ProjectSelection,
        swarm_id: str,
        work_id: str,
        request: GateApprovalRequest,
    ) -> dict[str, object]:
        self.calls.append((selection, swarm_id, work_id, request))
        if self.error:
            raise CommandAdapterError(self.error, f"safe {self.error} reason")
        return {
            "schema": "agora/application/gate-decision-projection/v1",
            "project_identity": selection.project,
            "swarm_id": swarm_id,
            "work_id": work_id,
            "gate_id": request.gate_id,
            "decision": request.decision,
        }


def selected_store() -> ProjectStore:
    store = ProjectStore()
    store._selection = ProjectSelection(Path("/tmp/governed-project"), "governed-project")
    return store


def payload(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "agora/application/approve-gate-command/v1",
        "gate_id": "completion",
        "actor_id": "project:owner",
        "decision": "approved",
        "reason": "Reviewed durable evidence",
        "expected_state": "verifying",
        "evidence_references": ["repo://reports/release.txt"],
    }
    value.update(changes)
    return value


class GateApprovalApiTests(unittest.TestCase):
    route = "/api/v1/work-items/delivery/release/approvals"

    def test_translates_http_to_the_versioned_core_command_without_browser_paths(self) -> None:
        commands = RecordingCommands()

        status, response = handle_api(
            selected_store(), "POST", self.route, payload(), commands=commands
        )

        self.assertEqual(200, status)
        self.assertEqual("persisted", response["status"])
        selection, swarm, work, request = commands.calls[0]
        self.assertEqual("governed-project", selection.project)
        self.assertEqual(("delivery", "release"), (swarm, work))
        self.assertEqual("completion", request.gate_id)
        self.assertEqual(("repo://reports/release.txt",), request.evidence_references)
        self.assertNotIn("path", payload())

    def test_requires_selection_and_a_compatible_serializable_contract(self) -> None:
        status, response = handle_api(
            ProjectStore(), "POST", self.route, payload(), commands=RecordingCommands()
        )
        self.assertEqual(409, status)
        self.assertEqual("project_required", response["error"])

        status, response = handle_api(
            selected_store(),
            "POST",
            self.route,
            payload(schema="agora/application/approve-gate-command/v2"),
            commands=RecordingCommands(),
        )
        self.assertEqual(426, status)
        self.assertEqual("command.version-incompatible", response["error"])

        status, response = handle_api(
            selected_store(),
            "POST",
            self.route,
            payload(path="/tmp/forbidden"),
            commands=RecordingCommands(),
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_request", response["error"])

    def test_rejects_unsafe_routes_and_invalid_decisions_before_core(self) -> None:
        commands = RecordingCommands()

        bad_route = "/api/v1/work-items/delivery/../approvals"
        self.assertEqual(404, handle_api(selected_store(), "POST", bad_route)[0])
        status, response = handle_api(
            selected_store(),
            "POST",
            self.route,
            payload(decision="maybe"),
            commands=commands,
        )

        self.assertEqual(400, status)
        self.assertEqual("invalid_request", response["error"])
        self.assertEqual([], commands.calls)

    def test_maps_core_errors_without_tracebacks(self) -> None:
        expected = {
            "command.actor-unauthorized": 403,
            "command.gate-already-resolved": 409,
            "command.stale-precondition": 409,
            "command.evidence-missing": 422,
            "command.signature-required": 428,
            "command.persistence-failed": 503,
            "command.version-incompatible": 426,
        }
        for code, expected_status in expected.items():
            with self.subTest(code=code):
                status, response = handle_api(
                    selected_store(),
                    "POST",
                    self.route,
                    payload(),
                    commands=RecordingCommands(code),
                )
                self.assertEqual(expected_status, status)
                self.assertEqual(code, response["error"])
                self.assertNotIn("traceback", json.dumps(response).lower())

    def test_network_adapter_enforces_json_content_type_and_bounded_body(self) -> None:
        source = (Path(__file__).parents[1] / "agora_studio" / "server.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('media_type != "application/json"', source)
        self.assertIn("_MAX_JSON_BODY = 65_536", source)
        self.assertIn("413", source)
        self.assertIn('("127.0.0.1", port)', source)


class GateApprovalUiTests(unittest.TestCase):
    static = Path(__file__).parents[1] / "agora_studio" / "static"

    def test_frontend_model_resolves_gate_actor_role_and_successful_evidence(self) -> None:
        model = self.static / "dashboard-model.js"
        script = f"""
require({json.dumps(str(model))});
const work = {{id:'release', swarm_id:'delivery'}};
const swarms = [{{id:'delivery', assignments:{{'product-owner':'project:owner'}}}}];
const detail = {{
  lifecycle: {{method: {{current_state:'verifying', transitions:[{{from:'verifying',to:'completed',gate:'completion',required_approval_roles:['product-owner'],blockers:['approvals missing']}}]}}}},
  artifacts: {{
    approvals: {{records:[],satisfaction:[]}},
    evidence: [{{type:'test-run',result:'success',artifact_references:['repo://report.txt']}},{{type:'lint',result:'failure',artifact_references:[]}}],
  }},
}};
process.stdout.write(JSON.stringify(DashboardModel.gateDecisionContext(work, swarms, detail)));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        context = json.loads(result.stdout)

        self.assertEqual("completion", context["gate"]["id"])
        self.assertEqual("product-owner", context["role"])
        self.assertEqual("project:owner", context["actor"])
        self.assertEqual(1, len(context["evidence"]))
        self.assertTrue(context["ready"])

    def test_ui_requires_reason_confirms_waits_and_refreshes_durable_projections(self) -> None:
        javascript = (self.static / "app.js").read_text(encoding="utf-8")

        for contract in (
            "Decision reason",
            'required: "required"',
            "Confirm governed mutation",
            "await requestJson",
            "await refreshAfterGateDecision",
            "Rejection persisted",
            "command.actor-unauthorized",
            "command.gate-already-resolved",
            "command.stale-precondition",
            "command.evidence-missing",
            "command.signature-required",
            "command.persistence-failed",
            "command.version-incompatible",
        ):
            self.assertIn(contract, javascript)
        self.assertNotIn("innerHTML", javascript)


if __name__ == "__main__":
    unittest.main()
