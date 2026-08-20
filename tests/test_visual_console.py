from __future__ import annotations

import json
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from agora_studio.core import AgoraCliBoundary, ProjectStore, SelectionError
from agora_studio.server import handle_api, static_response
from tests.test_foundation import make_project


class OverviewRunner:
    fixtures: dict[tuple[str, ...], object] = {
        ("status",): {
            "project": "visual-test",
            "branch": "agora/test",
            "default_method": "spec-driven",
            "integration": "codex",
            "counts": {"actors": 1, "swarms": 1, "work": 1, "sessions": 1, "tool-runs": 0},
            "swarm_statuses": {"running": 1},
            "work_states": {"implementing": 1},
            "attention": {"active-work": ["test/work"], "blocked-work": []},
        },
        ("actor", "list"): [{"name": "Agent", "reference": "project:agent", "kind": "ai-agent"}],
        ("swarm", "list"): [{"id": "test", "status": "running", "assignments": {}}],
        ("work", "list"): [{"id": "work", "swarm_id": "test", "state": "implementing"}],
        ("session", "list"): [{"id": "run-test", "status": "running"}],
    }

    def __init__(self, fail_on: tuple[str, ...] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        operation = tuple(command[3:])
        if operation == self.fail_on:
            return subprocess.CompletedProcess(command, 2, "", "fixture read failed")
        return subprocess.CompletedProcess(command, 0, json.dumps(self.fixtures[operation]), "")


class OverviewBoundaryTests(unittest.TestCase):
    def test_every_structured_read_uses_the_exact_allowlisted_argv(self) -> None:
        runner = OverviewRunner()
        boundary = AgoraCliBoundary(runner=runner)
        project = Path("/tmp/a project")

        for operation in boundary.allowed_operations:
            boundary.execute(operation, project)

        self.assertEqual(
            [
                ["agora", "--project", "/tmp/a project", "status"],
                ["agora", "--project", "/tmp/a project", "actor", "list"],
                ["agora", "--project", "/tmp/a project", "swarm", "list"],
                ["agora", "--project", "/tmp/a project", "work", "list"],
                ["agora", "--project", "/tmp/a project", "session", "list"],
            ],
            runner.calls,
        )
        with self.assertRaises(SelectionError):
            boundary.execute("work.transition", project)
        self.assertEqual(5, len(runner.calls))

    def test_operation_specific_json_shapes_are_enforced(self) -> None:
        def invalid_list(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 0, '{"unexpected": true}', "")

        with self.assertRaisesRegex(SelectionError, "invalid result"):
            AgoraCliBoundary(runner=invalid_list).execute("actors", Path("/tmp/project"))


class OverviewApiTests(unittest.TestCase):
    def test_overview_requires_a_selected_project(self) -> None:
        status, payload = handle_api(ProjectStore(), "GET", "/api/overview")

        self.assertEqual(409, status)
        self.assertEqual("project_required", payload["error"])

    def test_overview_aggregates_all_read_only_collections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory), "visual-test")
            runner = OverviewRunner()
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            store.select(str(project))

            status, payload = handle_api(store, "GET", "/api/overview")

        self.assertEqual(200, status)
        self.assertEqual("visual-test", payload["selection"]["project"])
        self.assertEqual("agora/test", payload["status"]["branch"])
        self.assertEqual("Agent", payload["actors"][0]["name"])
        self.assertEqual("test", payload["swarms"][0]["id"])
        self.assertEqual("work", payload["work"][0]["id"])
        self.assertEqual("run-test", payload["sessions"][0]["id"])

    def test_failed_overview_read_is_structured_and_preserves_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory), "visual-test")
            runner = OverviewRunner()
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            selected = store.select(str(project))
            runner.fail_on = ("work", "list")

            status, payload = handle_api(store, "GET", "/api/overview")

            self.assertEqual(502, status)
            self.assertEqual("project_overview_failed", payload["error"])
            self.assertEqual("work", payload["operation"])
            self.assertEqual(selected, store.selection)


class AssetAndUiContractTests(unittest.TestCase):
    static = Path(__file__).parents[1] / "agora_studio" / "static"

    def test_root_and_allowlisted_assets_have_expected_content_types(self) -> None:
        html, content_type, cache = static_response("/")
        self.assertEqual("text/html; charset=utf-8", content_type)
        self.assertFalse(cache)
        self.assertIn(b"Agora Studio", html)

        expected = {
            "/assets/styles.css": "text/css; charset=utf-8",
            "/assets/app.js": "text/javascript; charset=utf-8",
            "/assets/agora-logo.png": "image/png",
        }
        for route, content_type in expected.items():
            with self.subTest(route=route):
                body, actual_type, cache = static_response(route)
                self.assertEqual(content_type, actual_type)
                self.assertTrue(cache)
                self.assertTrue(body)

    def test_asset_traversal_and_unknown_files_are_rejected(self) -> None:
        for route in ("/assets/../server.py", "/assets/missing.css"):
            with self.subTest(route=route):
                self.assertIsNone(static_response(route))

    def test_semantic_accessible_and_responsive_contracts_are_present(self) -> None:
        html = (self.static / "index.html").read_text(encoding="utf-8")
        css = (self.static / "styles.css").read_text(encoding="utf-8")
        javascript = (self.static / "app.js").read_text(encoding="utf-8")

        self.assertEqual(1, html.count("<h1"))
        for contract in (
            "<main",
            "<nav",
            "<aside",
            "skip-link",
            'aria-live="polite"',
            "project-path-label",
        ):
            self.assertIn(contract, html)
        self.assertIn("/assets/agora-logo.png", html)
        self.assertNotIn("https://", html)
        self.assertIn(":focus-visible", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn("@media (max-width: 460px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("textContent", javascript)
        self.assertIn("replaceChildren", javascript)

        nav_items = [
            'data-view="overview"',
            'data-view="work"',
            'data-view="swarms"',
            'data-view="actors"',
            'data-view="activity"',
        ]
        for nav_item in nav_items:
            self.assertIn(nav_item, html)
        self.assertEqual(5, html.count("data-view="))
        self.assertIn('const API_ROOT = "/api/v1"', javascript)
        self.assertNotRegex(javascript, r'["`]\/api\/(?!v1)')

    def test_logo_asset_is_bundled_with_the_python_package(self) -> None:
        path = self.static / "agora-mark.png"
        payload = path.read_bytes()
        served, content_type, cache = static_response("/assets/agora-logo.png")

        self.assertEqual(payload, served)
        self.assertEqual("image/png", content_type)
        self.assertTrue(cache)
        self.assertEqual(b"\x89PNG\r\n\x1a\n", payload[:8])
        self.assertEqual(b"IHDR", payload[12:16])
        width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[16:26])
        self.assertEqual((192, 192), (width, height))
        self.assertEqual(8, bit_depth)
        self.assertEqual(6, color_type, "the package mark must use RGBA color")

    def test_overview_rejects_cli_json_below_the_minimum_compatibility_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory), "visual-test")
            runner = OverviewRunner()
            runner.fixtures = {**runner.fixtures, ("actor", "list"): [{"name": "Agent"}]}
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            store.select(str(project))

            status, payload = handle_api(store, "GET", "/api/overview")

        self.assertEqual(502, status)
        self.assertEqual("project_overview_failed", payload["error"])
        self.assertEqual("actors", payload["operation"])
        self.assertIn("minimum compatibility shape", payload["reason"])


if __name__ == "__main__":
    unittest.main()
