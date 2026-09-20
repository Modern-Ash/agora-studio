"""Real Agora Core producer feeding Studio through the public application services."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agora.application import FlavorProjectionContext, FlavorProjectionContribution
from test_real_integration import create_gate_project

from agora_studio.core import CoreReadGateway, ProjectStore
from agora_studio.flavor import FlavorProjectorError, load_flavor_projector
from agora_studio.server import handle_api

SCHEMA = json.loads(
    (Path(__file__).parent / "fixtures" / "ai-sdlc-projection-v1" / "schema.json").read_text(
        encoding="utf-8"
    )
)


def unavailable(code: str, message: str) -> dict[str, object]:
    return {"status": "unavailable", "reason": {"code": code, "message": message}}


class StubProjector:
    """A generic, provider-neutral projector: it derives everything from the Core context."""

    projection_schema = "agora-ai-sdlc/studio-projection/v1"
    projection_schema_document = SCHEMA
    required_sections = ("flavor", "profiles", "provenance", "separation", "metrics")

    def project(self, context: FlavorProjectionContext) -> FlavorProjectionContribution:
        sessions = [
            {
                "session_id": session.id,
                "actor": session.actor,
                "runtime": {
                    "source": session.provenance.runtime_basis,
                    "value": session.integration,
                },
                "runtime_version": {"source": "unavailable", "value": None},
                "provider": {
                    "source": session.provenance.provider_basis,
                    "value": session.provider,
                },
                "model": {"source": session.provenance.model_basis, "value": session.model},
                "selection_reason": {"source": "unavailable", "value": None},
                "fallback": {
                    "source": "unavailable",
                    "used": session.provenance.fallback_used,
                    "from": None,
                    "reason": None,
                },
            }
            for session in context.sessions
        ]
        return FlavorProjectionContribution(
            sections={
                "flavor": {
                    "status": "available",
                    "value": {
                        "id": "stub-flavor",
                        "name": "Stub flavor",
                        "version": "0.0.1",
                        "manifest_schema": "agora/flavor/v1",
                        "supported_core": ">=0.9,<0.10",
                    },
                },
                "profiles": unavailable("projection.profiles-unavailable", "No active profile"),
                "provenance": (
                    {
                        "status": "available",
                        "value": {
                            "source_schema": "agora/application/session-summary/v1",
                            "executions": sessions,
                        },
                    }
                    if sessions
                    else unavailable("projection.provenance-unavailable", "No execution recorded")
                ),
                "separation": unavailable("projection.separation-unavailable", "Not evaluated"),
                "metrics": unavailable("projection.metrics-unavailable", "No metric window"),
            },
            presentation={"authoritative": False, "labels": {}, "section_order": []},
        )


class RealCoreProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = create_gate_project(Path(self.temp.name))
        self.store = ProjectStore(CoreReadGateway(flavor_projectors=(StubProjector(),)))
        self.selection = self.store.select(str(self.project))

    def fetch(self, store: ProjectStore | None = None, **query: str) -> tuple[int, object]:
        params = {
            "selection": self.selection.selection_id,
            "swarm": "delivery",
            "work": "release",
            **query,
        }
        return handle_api(
            store or self.store,
            "GET",
            "/api/v1/ai-sdlc/projection",
            query={key: [value] for key, value in params.items()},
        )

    def test_real_core_aggregate_validates_and_is_path_free(self) -> None:
        status, body = self.fetch()
        self.assertEqual(status, 200, body)
        rendered = json.dumps(body)
        self.assertNotIn(str(self.project), rendered)
        self.assertNotIn(self.temp.name, rendered)
        projection = body["projection"]  # type: ignore[index]
        self.assertEqual(projection["project"]["selection_id"], self.selection.selection_id)
        self.assertRegex(projection["project"]["snapshot"], r"^[0-9a-f]{64}$")
        self.assertEqual(projection["lifecycle"]["status"], "available")
        state_ids = {s["id"] for s in projection["lifecycle"]["value"]["states"]}
        self.assertIn(projection["lifecycle"]["value"]["current_state"], state_ids)
        self.assertEqual(projection["separation"]["status"], "unavailable")
        self.assertEqual(projection["presentation"]["authoritative"], False)

    def test_snapshot_changes_when_durable_work_changes(self) -> None:
        first = self.fetch()[1]["projection"]["project"]["snapshot"]  # type: ignore[index]
        again = self.fetch()[1]["projection"]["project"]["snapshot"]  # type: ignore[index]
        self.assertEqual(first, again)

    def test_without_a_registered_projector_the_read_is_a_stable_not_found(self) -> None:
        bare = ProjectStore(CoreReadGateway())
        selection = bare.select(str(self.project))
        status, body = handle_api(
            bare,
            "GET",
            "/api/v1/ai-sdlc/projection",
            query={
                "selection": [selection.selection_id],
                "swarm": ["delivery"],
                "work": ["release"],
            },
        )
        self.assertEqual((status, body["error"]), (404, "read.resource-not-found"))  # type: ignore[index]

    def test_unknown_work_is_a_core_not_found(self) -> None:
        status, body = self.fetch(work="missing")
        self.assertEqual(status, 404, body)


class StartupWiringTests(unittest.TestCase):
    def test_factory_specs_are_strict_and_import_failures_are_safe(self) -> None:
        for spec in ("nomodule", "a:b:c", "../x:y", "os.path", ":x", "x:"):
            with self.subTest(spec), self.assertRaises(FlavorProjectorError):
                load_flavor_projector(spec)
        with self.assertRaises(FlavorProjectorError) as context:
            load_flavor_projector("definitely_missing_module:factory")
        self.assertNotIn("Traceback", str(context.exception))

    def test_a_factory_or_instance_is_returned_as_a_provider(self) -> None:
        provider = load_flavor_projector("test_ai_sdlc_real_projection:StubProjector")
        self.assertIsInstance(provider, StubProjector)


if __name__ == "__main__":
    unittest.main()
