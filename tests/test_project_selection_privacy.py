from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import FakeGateway

from agora_studio.core import ProjectStore, SelectionError
from agora_studio.server import handle_api


class ProjectSelectionPrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "payments-api"
        self.root.mkdir()

    def assertPathFree(self, body: object) -> None:
        rendered = json.dumps(body)
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn(self.temp.name, rendered)
        self.assertNotIn('"path"', rendered)

    def test_path_selection_and_session_never_echo_the_filesystem_path(self) -> None:
        store = ProjectStore(FakeGateway())
        status, opened = handle_api(
            store, "POST", "/api/v1/projects/select", {"path": str(self.root)}
        )
        self.assertEqual(status, 200)
        self.assertPathFree(opened)
        self.assertEqual(opened["project"]["schema"], "agora-studio/api/project-selection/v2")
        self.assertRegex(opened["project"]["selection_id"], r"^selected-")
        for route in ("/api/v1/project", "/api/v1/overview", "/api/v1/projects"):
            status, body = handle_api(store, "GET", route)
            self.assertEqual(status, 200, route)
            self.assertPathFree(body)

    def test_selection_errors_do_not_echo_the_requested_path(self) -> None:
        store = ProjectStore(FakeGateway())
        missing = str(self.root / "does-not-exist")
        for requested in (missing, str(self.root / "file-not-dir"), "", 7):
            status, body = handle_api(store, "POST", "/api/v1/projects/select", {"path": requested})
            self.assertEqual(status, 400)
            self.assertNotIn(self.temp.name, json.dumps(body))
            self.assertNotIn("path", body)

    def test_registered_projects_are_selected_by_stable_opaque_id(self) -> None:
        store = ProjectStore(FakeGateway())
        first = store.register(str(self.root))
        self.assertEqual(store.register(str(self.root)).selection_id, first.selection_id)
        status, listing = handle_api(store, "GET", "/api/v1/projects")
        self.assertEqual(status, 200)
        self.assertPathFree(listing)
        self.assertEqual(
            [item["selection_id"] for item in listing["projects"]], [first.selection_id]
        )
        status, opened = handle_api(
            store, "POST", "/api/v1/projects/select", {"selection_id": first.selection_id}
        )
        self.assertEqual(status, 200)
        self.assertPathFree(opened)
        self.assertEqual(opened["project"]["selection_id"], first.selection_id)
        self.assertEqual(store.selection.selection_id, first.selection_id)

    def test_unknown_or_forged_selection_ids_are_rejected(self) -> None:
        store = ProjectStore(FakeGateway())
        store.register(str(self.root))
        for forged in ("selected-forged", "", None, 5, str(self.root)):
            status, body = handle_api(
                store, "POST", "/api/v1/projects/select", {"selection_id": forged}
            )
            self.assertEqual(status, 400, forged)
            self.assertEqual(body["code"], "selection.unknown")
            self.assertIsNone(store.selection)

    def test_operator_can_disable_typed_path_entry(self) -> None:
        store = ProjectStore(FakeGateway(), allow_path_entry=False)
        registered = store.register(str(self.root))
        status, body = handle_api(
            store, "POST", "/api/v1/projects/select", {"path": str(self.root)}
        )
        self.assertEqual((status, body["code"]), (403, "selection.path-entry-disabled"))
        self.assertIsNone(store.selection)
        status, _ = handle_api(
            store, "POST", "/api/v1/projects/select", {"selection_id": registered.selection_id}
        )
        self.assertEqual(status, 200)
        status, session = handle_api(store, "GET", "/api/v1/project")
        self.assertFalse(session["path_entry"])
        with self.assertRaises(SelectionError):
            store.select(str(self.root))


if __name__ == "__main__":
    unittest.main()
