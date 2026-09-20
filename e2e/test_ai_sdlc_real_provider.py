"""Real Core + the real AI-SDLC projection provider + Chromium (Studio issue #10 / flavor issue #37)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

try:
    from agora_ai_sdlc.scenario import SWARM, WORK, Lifecycle
    from agora_ai_sdlc.studio_projection import projector

    AVAILABLE = True
except ImportError:  # the flavor is optional for Studio's own CI
    AVAILABLE = False

from agora.model import StartSessionInput, WorkActorInput
from agora.workspace import AgoraWorkspace

try:
    from .support import RunningStudio
except ImportError:
    from support import RunningStudio

from agora_studio.core import CoreReadGateway, ProjectStore

STATES = ["readiness", "intent", "inception", "construction", "operations", "completed"]


@unittest.skipUnless(
    AVAILABLE, "agora-ai-sdlc with the Studio projection provider is not installed"
)
class RealProviderChromiumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if executable is None and Path("/snap/bin/chromium").exists():
            executable = "/snap/bin/chromium"
        cls.browser = cls.playwright.chromium.launch(
            headless=True, executable_path=executable, args=["--no-sandbox"]
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {"AGORA_HOME": str(root / "home")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.life = Lifecycle(root / "project", root / "home")
        self.life.to_intent()
        self.life.to_inception()
        self.life.to_construction()
        store = ProjectStore(CoreReadGateway(flavor_projectors=(projector,)))
        self.studio = RunningStudio(store)
        self.addCleanup(self.studio.close)
        context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
        self.addCleanup(context.close)
        self.page = context.new_page()
        self.errors: list[str] = []
        self.requests: list[str] = []
        self.page.on("request", lambda request: self.requests.append(request.url))
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(f"http://127.0.0.1:{self.studio.port}/")
        self.page.locator("#project-path").fill(str(self.life.root))
        self.page.get_by_role("button", name="Open", exact=True).click()
        self.page.get_by_role("heading", name="Process status").wait_for()
        self.page.get_by_role("button", name="AI-SDLC", exact=True).click()
        self.page.locator("#ai-sdlc-work-select").select_option(f"{SWARM}/{WORK}")
        self.page.locator(".ai-sdlc-grid").wait_for()

    def test_real_provider_projects_core_lifecycle_flavor_and_blocked_gates(self) -> None:
        page = self.page
        ids = page.locator("[data-state-id]").evaluate_all(
            "nodes => nodes.map(n => n.dataset.stateId)"
        )
        self.assertEqual(ids, STATES)
        self.assertEqual(
            page.locator("[data-state-id][aria-current='step']").get_attribute("data-state-id"),
            "construction",
        )
        self.assertEqual(
            page.locator("[data-section='flavor']").get_attribute("data-status"), "available"
        )
        self.assertIn("AI-SDLC", page.locator("[data-section='flavor']").inner_text())
        blocked = page.locator("[data-transition='construction>operations']")
        self.assertIn("blocked", blocked.inner_text().lower())
        self.assertGreaterEqual(blocked.locator(".blocker-text").count(), 3)
        self.assertIn("Required approval roles are missing", blocked.inner_text())
        for section in ("profiles", "separation", "metrics", "provenance"):
            self.assertEqual(
                page.locator(f"[data-section='{section}']").get_attribute("data-status"),
                "unavailable",
                section,
            )
        self.assertEqual(self.errors, [])

    def test_open_clarification_and_session_provenance_come_from_core(self) -> None:
        def asking(command, cwd, environment):
            body = {
                "questions": [
                    {"question": "Which timeout is contractually supported?", "answer": None}
                ]
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(body), "")

        AgoraWorkspace(cwd=self.life.root, tool_runner=asking).clarify_work(
            WorkActorInput(swarm_id=SWARM, work_id=WORK, actor_id="po"), runner="/bin/true"
        )
        self.life.ws.start_session(
            StartSessionInput(id="build-1", actor_id="build", swarm_id=SWARM, work_id=WORK)
        )
        self.page.get_by_role("button", name="Refresh").click()
        self.page.locator("[data-session='build-1']").wait_for()
        queue = self.page.locator("[data-clarification]")
        self.assertIn("Which timeout is contractually supported?", queue.inner_text())
        execution = self.page.locator("[data-session='build-1']").inner_text().lower()
        self.assertIn("declared", execution)
        self.assertNotIn("observed", execution)
        self.assertIn("not used", execution)

    def test_stale_refresh_shows_the_new_snapshot_and_lifecycle_state(self) -> None:
        before = self.page.locator("[data-snapshot]").get_attribute("data-snapshot")
        self.life.to_operations()
        self.page.get_by_role("button", name="Refresh").click()
        self.page.locator("[data-ai-sdlc-notice]").wait_for()
        self.assertNotEqual(
            self.page.locator("[data-snapshot]").get_attribute("data-snapshot"), before
        )
        self.assertEqual(
            self.page.locator("[data-state-id][aria-current='step']").get_attribute(
                "data-state-id"
            ),
            "operations",
        )

    def test_ai_sdlc_view_never_exposes_the_project_path_or_credentials(self) -> None:
        content = self.page.locator("#content")
        self.assertNotIn(str(self.life.root), content.inner_html())
        self.assertNotIn("PRIVATE KEY", content.inner_html())
        self.assertNotIn(str(self.life.root), " ".join(self.requests))


if __name__ == "__main__":
    unittest.main()
