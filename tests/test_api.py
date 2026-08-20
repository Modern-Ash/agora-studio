from __future__ import annotations

import tempfile
import unittest

from agora_studio.commands import CommandAdapterError
from agora_studio.core import CoreGatewayError, ProjectStore
from agora_studio.server import handle_api
from tests.support import FakeGateway


class FakeCommands:
    def __init__(self, error: CommandAdapterError | None = None) -> None:
        self.error = error
        self.requests = []

    def approve_gate(self, selection, swarm_id, work_id, request):
        self.requests.append((selection, swarm_id, work_id, request))
        if self.error:
            raise self.error
        return {
            "schema": "agora/application/gate-decision-projection/v1",
            "project_identity": selection.project,
            "swarm_id": swarm_id,
            "work_id": work_id,
            "gate_id": request.gate_id,
            "actor_id": request.actor_id,
            "role_id": request.role_id,
            "decision": request.decision,
            "reason": request.reason,
            "lifecycle": {"schema": "agora/application/lifecycle-projection/v2"},
            "activity": {"schema": "agora/application/activity-entry/v1"},
        }

    def prepare_gate(self, selection, swarm_id, work_id, request):
        self.requests.append((selection, swarm_id, work_id, request))
        if self.error:
            raise self.error
        return {
            "schema": "agora/application/prepared-gate-decision/v1",
            "project_identity": selection.project,
            "swarm_id": swarm_id,
            "work_id": work_id,
            "gate_id": request.gate_id,
            "actor_id": request.actor_id,
            "role_id": request.role_id,
            "decision": request.decision,
            "authorization_payload": "canonical\n",
        }


def command_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "agora/application/approve-gate-command/v2",
        "gate_id": "completion",
        "actor_id": "project:owner",
        "decision": "approved",
        "reason": "Verified evidence",
        "expected_state": "verifying",
        "transition_target": "completed",
        "role_id": "product-owner",
        "evidence_references": ["repo://report"],
    }
    payload.update(changes)
    return payload


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.gateway = FakeGateway()
        self.store = ProjectStore(self.gateway)
        self.store.select(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_every_read_route_is_versioned_and_core_backed(self) -> None:
        routes = {
            "/api/v1/overview": "agora-studio/api/overview/v1",
            "/api/v1/actors": "agora-studio/api/actors/v1",
            "/api/v1/swarms": "agora-studio/api/swarms/v1",
            "/api/v1/work-items": "agora-studio/api/work-items/v1",
            "/api/v1/sessions": "agora-studio/api/sessions/v1",
            "/api/v1/activity": "agora-studio/api/activity/v1",
            "/api/v1/lifecycle": "agora-studio/api/lifecycle/v1",
            "/api/v1/artifacts": "agora-studio/api/work-materials/v1",
            "/api/v1/evidence": "agora-studio/api/evidence/v1",
            "/api/v1/approvals": "agora-studio/api/approvals/v1",
            "/api/v1/traceability": "agora-studio/api/traceability/v1",
            "/api/v1/specification-history": "agora-studio/api/specification-history/v1",
            "/api/v1/specification-revisions/working-tree": "agora-studio/api/specification-revision-detail/v1",
            "/api/v1/work-items/delivery/release": "agora-studio/api/work-item-detail/v2",
        }
        query = {"swarm": "delivery", "work": "release"}
        for route, schema in routes.items():
            with self.subTest(route=route):
                status, payload = handle_api(
                    self.store,
                    "GET",
                    route,
                    query=query
                    if route.startswith("/api/v1/specification-revisions/")
                    or route.rsplit("/", 1)[-1]
                    in {
                        "lifecycle",
                        "artifacts",
                        "evidence",
                        "approvals",
                        "traceability",
                        "specification-history",
                    }
                    else None,
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["schema"], schema)
                if route == "/api/v1/artifacts":
                    self.assertNotIn("missing_roles", payload["approvals"])
                    self.assertEqual(
                        payload["approvals"]["gate_decision_options"]["schema"],
                        "agora/application/gate-decision-options-projection/v1",
                    )

    def test_legacy_aliases_are_removed(self) -> None:
        for route in ("/api/overview", "/api/activity", "/api/lifecycle", "/api/artifacts"):
            status, payload = handle_api(self.store, "GET", route)
            self.assertEqual(status, 404)
            self.assertEqual(payload["error"], "not_found")

    def test_partial_specification_is_data_not_transport_failure(self) -> None:
        status, payload = handle_api(
            self.store,
            "GET",
            "/api/v1/specification-history",
            query={"swarm": "delivery", "work": "release"},
        )
        self.assertEqual(status, 200)
        self.assertFalse(payload["specification"]["available"])
        self.assertEqual(
            payload["specification"]["schema"], "agora/application/specification-summary/v1"
        )

    def test_core_errors_are_stable_and_do_not_leak_tracebacks(self) -> None:
        self.gateway.failure = CoreGatewayError("core.schema-incompatible", "wrong schema")
        status, payload = handle_api(self.store, "GET", "/api/v1/overview")
        self.assertEqual(status, 426)
        self.assertEqual(payload["schema"], "agora-studio/api/error/v1")
        self.assertEqual(payload["error"], "core.schema-incompatible")
        self.assertNotIn("traceback", str(payload).lower())

    def test_gate_decision_maps_command_and_errors_without_business_rules(self) -> None:
        commands = FakeCommands()
        route = "/api/v1/work-items/delivery/release/approvals"
        status, payload = handle_api(
            self.store, "POST", route, command_payload(), commands=commands
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "persisted")
        self.assertEqual(commands.requests[0][3].decision, "approved")
        self.assertEqual(commands.requests[0][3].role_id, "product-owner")

        status, prepared = handle_api(
            self.store,
            "POST",
            f"{route}/prepare",
            command_payload(),
            commands=commands,
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            prepared["preparation"]["schema"],
            "agora/application/prepared-gate-decision/v1",
        )

        commands.error = CommandAdapterError(
            "command.stale-precondition", "the expected state is stale"
        )
        status, payload = handle_api(
            self.store, "POST", route, command_payload(), commands=commands
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "command.stale-precondition")

        commands.error = CommandAdapterError(
            "command.persistence-failed", "the durable transaction was rolled back"
        )
        status, payload = handle_api(
            self.store, "POST", route, command_payload(), commands=commands
        )
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"], "command.persistence-failed")

        commands.error = CommandAdapterError(
            "command.signature-required", "the actor must provide a detached signature"
        )
        status, payload = handle_api(
            self.store, "POST", route, command_payload(), commands=commands
        )
        self.assertEqual(status, 428)
        self.assertEqual(payload["error"], "command.signature-required")

        commands.error = CommandAdapterError(
            "core.schema-incompatible", "the durable projection is not compatible"
        )
        status, payload = handle_api(
            self.store, "POST", route, command_payload(), commands=commands
        )
        self.assertEqual(status, 426)
        self.assertEqual(payload["error"], "core.schema-incompatible")

    def test_invalid_slugs_and_missing_selection_fail_before_core(self) -> None:
        status, payload = handle_api(
            self.store,
            "GET",
            "/api/v1/lifecycle",
            query={"swarm": "../escape", "work": "release"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_query")
        empty = ProjectStore(FakeGateway())
        status, payload = handle_api(empty, "GET", "/api/v1/overview")
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "project_required")


if __name__ == "__main__":
    unittest.main()
