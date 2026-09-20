from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from support import FakeGateway

from agora_studio.core import CoreGatewayError, ProjectStore
from agora_studio.projection import ProjectionError, validate_projection
from agora_studio.server import handle_api

FIXTURES = Path(__file__).parent / "fixtures" / "ai-sdlc-projection-v1"
IDENTITY = {
    "selection_id": "selected-01J7W9X4",
    "project": "payments-api",
    "swarm_id": "delivery",
    "work_id": "idempotent-capture",
}


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def validate(payload: dict[str, object]) -> dict[str, object]:
    project = payload["project"]
    return validate_projection(
        payload,
        selection_id=project["selection_id"],  # type: ignore[index]
        project=project["id"],  # type: ignore[index]
        swarm_id=project["swarm_id"],  # type: ignore[index]
        work_id=project["work_id"],  # type: ignore[index]
    )


class ProjectionContractTests(unittest.TestCase):
    def test_complete_unavailable_and_future_fixtures_are_accepted(self) -> None:
        for name in ("complete", "unavailable", "future-state"):
            with self.subTest(name):
                self.assertEqual(validate(fixture(name)), fixture(name))

    def test_unavailable_sections_stay_independent_and_unknown_fields_survive(self) -> None:
        future = validate(fixture("future-state"))
        self.assertEqual(future["provenance"]["status"], "unavailable")  # type: ignore[index]
        self.assertEqual(future["lifecycle"]["status"], "available")  # type: ignore[index]
        self.assertIn("future_top_level_section", future)
        states = {s["id"] for s in future["lifecycle"]["value"]["states"]}  # type: ignore[index]
        self.assertTrue(
            states - {"readiness", "intent", "inception", "construction", "operations", "completed"}
        )

    def test_input_is_not_mutated_and_output_is_a_copy(self) -> None:
        source = fixture("complete")
        before = copy.deepcopy(source)
        result = validate(source)
        result["flavor"]["status"] = "changed"  # type: ignore[index]
        self.assertEqual(source, before)

    def assertRejected(self, payload: object, code: str, **override: str) -> None:
        with self.assertRaises(ProjectionError) as context:
            validate_projection(payload, **{**IDENTITY, **override})
        self.assertEqual(context.exception.code, code)

    def test_unsupported_and_foreign_schema_ids_are_rejected(self) -> None:
        for schema, code in (
            ("agora-ai-sdlc/studio-projection/v2", "projection.unsupported-version"),
            ("agora-ai-sdlc/studio-projection/v10", "projection.unsupported-version"),
            ("something/else/v1", "projection.malformed"),
        ):
            payload = fixture("complete")
            payload["schema"] = schema
            self.assertRejected(payload, code)
        self.assertRejected([], "projection.malformed")

    def test_every_required_section_is_mandatory(self) -> None:
        for name in (
            "flavor",
            "profiles",
            "lifecycle",
            "clarifications",
            "provenance",
            "separation",
            "metrics",
        ):
            payload = fixture("complete")
            del payload[name]
            self.assertRejected(payload, "projection.missing-section")
        payload = fixture("complete")
        del payload["presentation"]
        self.assertRejected(payload, "projection.malformed")

    def test_malformed_availability_envelopes_fail_closed(self) -> None:
        cases: list[dict[str, object]] = [
            {"status": "available"},
            {"status": "available", "value": None},
            {"status": "unavailable"},
            {"status": "unavailable", "reason": {"code": "x"}},
            {"status": "unavailable", "reason": {"code": "x", "message": "m"}, "value": {}},
            {"status": "maybe", "value": {}},
            None,
            [],
        ]
        for case in cases:
            payload = fixture("complete")
            payload["metrics"] = case  # type: ignore[assignment]
            with self.subTest(case=case):
                self.assertRejected(payload, "projection.malformed")

    def test_snapshot_and_identity_conflicts_are_rejected(self) -> None:
        for bad in ("", "AAAA", "g" * 64, "a" * 63, 7, None):
            payload = fixture("complete")
            payload["project"]["snapshot"] = bad  # type: ignore[index]
            self.assertRejected(payload, "projection.malformed-snapshot")
        for key, expected in (
            ("selection_id", "selected-other"),
            ("project", "other-project"),
            ("swarm_id", "other-swarm"),
            ("work_id", "other-work"),
        ):
            self.assertRejected(
                fixture("complete"), "projection.identity-mismatch", **{key: expected}
            )

    def test_contradictory_lifecycle_identity_is_rejected(self) -> None:
        mutations = {
            "current not declared": lambda v: v.update(current_state="ghost"),
            "terminal not declared": lambda v: v.update(terminal_state="ghost"),
            "duplicate ids": lambda v: v["states"].append(dict(v["states"][0])),
            "no states": lambda v: v.update(states=[]),
            "blank transition target": lambda v: v["transitions"][0].update(target=""),
        }
        for label, mutate in mutations.items():
            payload = fixture("complete")
            mutate(payload["lifecycle"]["value"])  # type: ignore[index]
            with self.subTest(label):
                with self.assertRaises(ProjectionError):
                    validate(payload)

    def test_presentation_can_never_be_authoritative(self) -> None:
        for value in (True, None, "false", 0):
            payload = fixture("complete")
            payload["presentation"]["authoritative"] = value  # type: ignore[index]
            self.assertRejected(payload, "projection.presentation-authoritative")

    def test_paths_endpoints_and_credentials_never_reach_the_browser(self) -> None:
        for leak in (
            "/home/user/project",
            "~/secrets",
            "../escape",
            "C:\\Users\\dev",
            "https://api.example.com/v1",
            "file:///etc/passwd",
            "-----BEGIN PRIVATE KEY-----",
            "sk-abcdefghijklmnop",
            "ghp_abcdefghijklmnop",
        ):
            payload = fixture("complete")
            payload["clarifications"]["value"]["open"][0]["question"] = f"see {leak}"  # type: ignore[index]
            with self.subTest(leak):
                self.assertRejected(payload, "projection.unsafe-content")
        payload = fixture("complete")
        payload["future_field"] = {"nested": ["ok", "/etc/passwd"]}
        self.assertRejected(payload, "projection.unsafe-content")


class ProjectionEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "payments-api"
        self.root.mkdir()
        self.gateway = FakeGateway()
        self.store = ProjectStore(self.gateway)
        self.selection = self.store.select(str(self.root))
        self.gateway.calls.clear()

    def payload(self, name: str = "complete") -> dict[str, object]:
        payload = fixture(name)
        payload["project"]["selection_id"] = self.selection.selection_id  # type: ignore[index]
        return payload

    def request(self, **query: str) -> tuple[int, object]:
        params = {
            "selection": self.selection.selection_id,
            "swarm": "delivery",
            "work": "idempotent-capture",
            **query,
        }
        return handle_api(
            self.store,
            "GET",
            "/api/v1/ai-sdlc/projection",
            query={k: [v] for k, v in params.items()},
        )

    def test_response_is_validated_and_never_exposes_a_filesystem_path(self) -> None:
        self.gateway.projection = self.payload()
        status, body = self.request()
        self.assertEqual(status, 200, body)
        rendered = json.dumps(body)
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn(self.temp.name, rendered)
        self.assertNotIn("csrf", rendered.lower())
        self.assertEqual(body["selection"]["selection_id"], self.selection.selection_id)  # type: ignore[index]
        self.assertNotIn("path", body["selection"])  # type: ignore[index]
        call = self.gateway.calls[0]
        self.assertEqual(call[2:], (self.selection.selection_id, "delivery", "idempotent-capture"))

    def test_opaque_selection_ids_are_server_issued_and_per_selection(self) -> None:
        other = self.store.select(str(self.root))
        self.assertNotEqual(other.selection_id, self.selection.selection_id)
        self.assertRegex(other.selection_id, r"^selected-[A-Za-z0-9_-]{16}$")

    def test_stale_or_forged_selection_ids_are_rejected_before_core_is_read(self) -> None:
        self.gateway.projection = self.payload()
        for forged in ("selected-forged", "", "../../etc"):
            status, body = self.request(selection=forged)
            self.assertEqual(status, 409, body)
            self.assertEqual(body["error"], "selection_stale")  # type: ignore[index]
        self.assertEqual(self.gateway.calls, [])

    def test_invalid_scope_is_rejected_without_calling_core(self) -> None:
        for kwargs in ({"swarm": "../x"}, {"work": "A B"}, {"work": ""}):
            status, body = self.request(**kwargs)
            self.assertEqual(status, 400, body)
        self.assertEqual(self.gateway.calls, [])

    def test_missing_projector_reports_core_not_found_without_guessing(self) -> None:
        status, body = self.request()
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "read.resource-not-found")  # type: ignore[index]

    def test_incompatible_aggregates_map_to_safe_errors(self) -> None:
        cases = (
            ("agora-ai-sdlc/studio-projection/v2", 426, "projection.unsupported-version"),
            ("other/thing/v1", 502, "projection.malformed"),
        )
        for schema, status, code in cases:
            payload = self.payload()
            payload["schema"] = schema
            self.gateway.projection = payload
            got_status, body = self.request()
            self.assertEqual((got_status, body["error"]), (status, code))  # type: ignore[index]
        payload = self.payload()
        payload["project"]["id"] = "someone-else"  # type: ignore[index]
        self.gateway.projection = payload
        status, body = self.request()
        self.assertEqual((status, body["error"]), (502, "projection.identity-mismatch"))  # type: ignore[index]

    def test_core_failures_pass_through_their_stable_code(self) -> None:
        self.gateway.failure = CoreGatewayError("durable-state.concurrent-edit", "changed")
        status, body = self.request()
        self.assertEqual(status, 502)
        self.assertEqual(body["error"], "durable-state.concurrent-edit")  # type: ignore[index]

    def test_no_selection_requires_a_project(self) -> None:
        store = ProjectStore(FakeGateway())
        status, body = handle_api(
            store,
            "GET",
            "/api/v1/ai-sdlc/projection",
            query={"selection": ["x"], "swarm": ["delivery"], "work": ["w"]},
        )
        self.assertEqual((status, body["error"]), (409, "project_required"))  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
