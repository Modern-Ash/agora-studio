from __future__ import annotations

import inspect
import tempfile
import unittest
from copy import deepcopy
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
            gate_decision_ttl_seconds=3600,
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


class DictDTO:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, object]:
        return self.payload


class NestedSchemaService(ReadServiceStub):
    def __init__(self, mutation) -> None:
        super().__init__()
        self.mutation = mutation

    def work_control_projection(self, swarm: str, work: str) -> DictDTO:
        payload = deepcopy(FakeGateway().work_control(Path("/tmp/demo"), swarm, work))
        self.mutation(payload)
        return DictDTO(payload)


class LegacyWorkControlService(ReadServiceStub):
    def work_control_projection(self, swarm: str, work: str):
        class LegacyControl:
            def to_dict(self):
                return {
                    "schema": "agora/application/work-control-projection/v1",
                    "work": {"schema": "agora/application/work-item-detail/v1"},
                    "lifecycle": {"schema": "agora/application/lifecycle-projection/v3"},
                    "traceability": {"schema": "agora/application/traceability-summary/v2"},
                    "specification_history": {
                        "schema": "agora/application/specification-summary/v1"
                    },
                    "gate_decision_options": {
                        "schema": "agora/application/gate-decision-options-projection/v1"
                    },
                }

        return LegacyControl()


class CoreGatewayTests(unittest.TestCase):
    def test_maps_public_dtos_and_exact_activity_filters(self) -> None:
        service = ReadServiceStub()
        gateway = CoreReadGateway(lambda _: service, core_version="0.8.0")

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

        self.assertEqual(overview["schema"], "agora/application/project-overview/v2")
        self.assertEqual(events[0]["schema"], "agora/application/activity-entry/v1")
        self.assertEqual(service.activity_filters.actor_id, "project:owner")
        self.assertEqual(service.activity_filters.limit, 25)

    def test_rejects_incompatible_core_and_schema(self) -> None:
        with self.assertRaisesRegex(CoreGatewayError, ">=0.8,<0.9"):
            CoreReadGateway(lambda _: ReadServiceStub(), core_version="0.4.9").core_version
        with self.assertRaisesRegex(CoreGatewayError, "project-overview/v2"):
            CoreReadGateway(lambda _: BadService(), core_version="0.8.0").project_overview(
                Path("/tmp/demo")
            )
        with self.assertRaises(CoreGatewayError) as legacy:
            CoreReadGateway(
                lambda _: LegacyWorkControlService(), core_version="0.8.0"
            ).work_control(Path("/tmp/demo"), "delivery", "release")
        self.assertEqual(legacy.exception.code, "core.schema-incompatible")
        self.assertIn("work-control-projection/v3", legacy.exception.reason)

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

    def test_rejects_malformed_nested_control_contracts(self) -> None:
        mutations = {
            "future option schema": lambda value: value["gate_decision_options"]["options"][
                0
            ].update({"schema": "agora/application/gate-decision-option-summary/v99"}),
            "non-array materials": lambda value: value.update({"artifacts": {}}),
            "changed option identity": lambda value: value["gate_decision_options"]["options"][
                0
            ].update({"work_id": "other"}),
            "invalid snapshot": lambda value: value.update({"snapshot_token": "stale"}),
            "invalid typed evidence": lambda value: value["gate_decision_options"]["options"][
                0
            ].update({"evidence_references_by_type": []}),
            "inconsistent lifecycle state": lambda value: value["lifecycle"].update(
                {"current_state": "reviewing"}
            ),
            "inconsistent operational status": lambda value: value["gate_decision_options"].update(
                {"operational_status": "blocked"}
            ),
            "inconsistent top-level materials": lambda value: value.update({"artifacts": []}),
            "inconsistent traceability materials": lambda value: value["traceability"].update(
                {"evidence": []}
            ),
            "typed evidence outside reference union": lambda value: value["gate_decision_options"][
                "options"
            ][0].update({"evidence_references_by_type": {"test-run": ["repo://other"]}}),
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                gateway = CoreReadGateway(
                    lambda _: NestedSchemaService(mutation), core_version="0.8.0"
                )
                with self.assertRaises(CoreGatewayError) as captured:
                    gateway.work_control(Path("/tmp/demo"), "delivery", "release")
                self.assertEqual(captured.exception.code, "core.schema-incompatible")


class ProjectStoreTests(unittest.TestCase):
    def test_selection_is_atomic_and_core_validated(self) -> None:
        gateway = FakeGateway()
        store = ProjectStore(gateway)
        with tempfile.TemporaryDirectory() as directory:
            selected = store.select(directory)
            self.assertEqual(selected.project, Path(directory).name)
            self.assertEqual(selected.core_version, "0.8.0")
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
        self.assertEqual(payload["status"]["schema"], "agora/application/project-overview/v2")
        self.assertTrue(payload["actors"])
        self.assertTrue(payload["work"])


if __name__ == "__main__":
    unittest.main()
