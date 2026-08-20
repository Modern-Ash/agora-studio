from __future__ import annotations

import inspect
import tempfile
import unittest
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from agora.application import ActivityEntry, ProjectOverview

from agora_studio.core import (
    ActivityQuery,
    CoreGatewayError,
    CoreReadGateway,
    ProjectStore,
)
from tests.support import FakeGateway


class ReadServiceStub:
    def __init__(self) -> None:
        self.activity_filters = None

    def project_overview(self) -> ProjectOverview:
        return ProjectOverview(
            project="demo",
            version="0.3.0",
            integration="generic",
            provider="local",
            model="local",
            default_method="scrum",
            max_delegation_depth=3,
            created_at="2026-08-20T12:00:00Z",
            branch="main",
            counts={},
            swarm_statuses={},
            work_states={},
            work_operational_statuses={},
            delegation_statuses={},
            session_statuses={},
            tool_run_statuses={},
            attention={},
        )

    def activity(self, filters: object) -> tuple[ActivityEntry, ...]:
        self.activity_filters = filters
        return (
            ActivityEntry(
                timestamp="2026-08-20T12:00:00Z",
                type="work.created",
                summary="work=release",
                actor="project:owner",
                swarm_id="delivery",
                work_id="release",
                session_id=None,
                tool_run_id=None,
                source="repo://events",
            ),
        )


class BadDTO:
    def to_dict(self) -> dict[str, str]:
        return {"schema": "agora/application/project-overview/v99"}


class BadService(ReadServiceStub):
    def project_overview(self) -> BadDTO:
        return BadDTO()


class CoreGatewayTests(unittest.TestCase):
    def test_maps_public_dtos_and_exact_activity_filters(self) -> None:
        service = ReadServiceStub()
        gateway = CoreReadGateway(lambda _: service, core_version="0.5.0")

        overview = gateway.project_overview(Path("/tmp/demo"))
        events = gateway.activity(
            Path("/tmp/demo"),
            ActivityQuery(
                {
                    "type": "work.created",
                    "actor": "project:owner",
                    "swarm": "delivery",
                    "work": "release",
                    "session": None,
                    "tool_run": None,
                },
                25,
            ),
        )

        self.assertEqual(overview["schema"], "agora/application/project-overview/v1")
        self.assertEqual(events[0]["schema"], "agora/application/activity-entry/v1")
        self.assertEqual(service.activity_filters.actor_id, "project:owner")
        self.assertEqual(service.activity_filters.limit, 25)

    def test_rejects_incompatible_core_and_schema(self) -> None:
        with self.assertRaisesRegex(CoreGatewayError, ">=0.5,<0.6"):
            CoreReadGateway(lambda _: ReadServiceStub(), core_version="0.4.9").core_version
        with self.assertRaisesRegex(CoreGatewayError, "project-overview/v1"):
            CoreReadGateway(lambda _: BadService(), core_version="0.5.0").project_overview(
                Path("/tmp/demo")
            )

    def test_reports_core_absence_without_cli_fallback(self) -> None:
        with patch("agora_studio.core.version", side_effect=PackageNotFoundError("missing")):
            gateway = CoreReadGateway()
            with self.assertRaises(CoreGatewayError) as captured:
                gateway.core_version
        self.assertEqual(captured.exception.code, "core.unavailable")
        import agora_studio.core as module

        source = inspect.getsource(module)
        self.assertNotIn("AgoraCliBoundary", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("shell=", source)


class ProjectStoreTests(unittest.TestCase):
    def test_selection_is_atomic_and_core_validated(self) -> None:
        gateway = FakeGateway()
        store = ProjectStore(gateway)
        with tempfile.TemporaryDirectory() as directory:
            selected = store.select(directory)
            self.assertEqual(selected.project, Path(directory).name)
            self.assertEqual(selected.core_version, "0.5.0")
            with self.assertRaises(Exception):
                store.select(Path(directory) / "missing")
            self.assertEqual(store.selection, selected)

    def test_overview_uses_only_gateway_results(self) -> None:
        gateway = FakeGateway()
        store = ProjectStore(gateway)
        with tempfile.TemporaryDirectory() as directory:
            store.select(directory)
            payload = store.overview()
        self.assertEqual(payload["schema"], "agora-studio/api/overview/v1")
        self.assertEqual(payload["status"]["schema"], "agora/application/project-overview/v1")
        self.assertTrue(payload["actors"])
        self.assertTrue(payload["work"])


if __name__ == "__main__":
    unittest.main()
