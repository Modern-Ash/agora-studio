from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

try:
    from .support import RunningStudio, create_gate_project
except ImportError:  # Direct execution from an installed-wheel verification directory.
    from support import RunningStudio, create_gate_project

from agora_studio.core import CoreReadGateway, ProjectStore


class ProjectSelectionPrivacyTests(unittest.TestCase):
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
        environment = patch.dict(os.environ, {"AGORA_HOME": str(root / "home")})
        environment.start()
        self.addCleanup(environment.stop)
        self.project = create_gate_project(root)

    def open_page(self, store: ProjectStore):
        studio = RunningStudio(store)
        self.addCleanup(studio.close)
        context = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.addCleanup(context.close)
        page = context.new_page()
        self.bodies: list[str] = []
        self.urls: list[str] = []
        page.on(
            "request", lambda request: self.urls.append(request.url + (request.post_data or ""))
        )
        page.on(
            "response",
            lambda response: (
                self.bodies.append(response.text()) if "/api/v1/" in response.url else None
            ),
        )
        page.goto(f"http://127.0.0.1:{studio.port}/")
        return page

    def assertNoPath(self, page) -> None:
        secret = str(self.project)
        self.assertNotIn(secret, page.content())
        self.assertNotIn(self.temporary.name, page.content())
        for body in self.bodies:
            self.assertNotIn(self.temporary.name, body)
        self.assertNotIn(self.temporary.name, " ".join(self.urls))

    def test_operator_registered_project_opens_without_any_typed_or_visible_path(self) -> None:
        store = ProjectStore(CoreReadGateway(), allow_path_entry=False)
        store.register(str(self.project))
        page = self.open_page(store)
        page.locator("#project-choice").wait_for()
        self.assertFalse(page.locator("#project-path").is_visible())
        self.assertEqual(page.locator("#project-choice option").count(), 1)
        page.get_by_role("button", name="Open", exact=True).click()
        page.get_by_role("heading", name="Process status").wait_for()
        page.locator("#selected-project-name").wait_for()
        self.assertEqual(page.locator("#selected-project-name").inner_text(), self.project.name)
        self.assertIsNone(page.locator("#selected-project-name").get_attribute("title"))
        page.get_by_role("button", name="Work", exact=True).click()
        page.get_by_role("heading", name="Work control").wait_for()
        self.assertNoPath(page)

    def test_typed_path_still_works_but_is_never_echoed_back(self) -> None:
        page = self.open_page(ProjectStore(CoreReadGateway()))
        page.locator("#project-path").fill(str(self.project))
        page.get_by_role("button", name="Open", exact=True).click()
        page.get_by_role("heading", name="Process status").wait_for()
        page.locator("#selected-project-name").wait_for()
        self.assertEqual(page.locator("#project-path").input_value(), "")
        self.assertIsNone(page.locator("#selected-project-name").get_attribute("title"))
        secret = str(self.project)
        self.assertNotIn(secret, page.content())
        for body in self.bodies:
            self.assertNotIn(secret, body)

    def test_invalid_typed_path_error_does_not_echo_the_path(self) -> None:
        page = self.open_page(ProjectStore(CoreReadGateway()))
        missing = str(Path(self.temporary.name) / "nowhere")
        page.locator("#project-path").fill(missing)
        page.get_by_role("button", name="Open", exact=True).click()
        page.locator("#project-path-error:not(:empty)").wait_for()
        self.assertNotIn(missing, page.locator("#project-path-error").inner_text())
        self.assertNotIn(missing, " ".join(self.bodies))


if __name__ == "__main__":
    unittest.main()
