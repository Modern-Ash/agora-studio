from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agora.application import FlavorProjectionContribution
from agora.model import TransitionWorkInput
from agora.workspace import AgoraWorkspace
from playwright.sync_api import Browser, Page, sync_playwright

try:
    from .support import RunningStudio, create_gate_project
except ImportError:  # Direct execution from an installed-wheel verification directory.
    from support import RunningStudio, create_gate_project

from agora_studio.core import CoreReadGateway, ProjectStore

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures" / "ai-sdlc-projection-v1"


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FixtureGateway:
    """Serve a contract fixture rebound to the selected work; Studio still validates it."""

    core_version = "0.9.0"

    def __init__(self, base) -> None:
        self._base = base
        self.payload: dict[str, object] = load("complete")

    def __getattr__(self, name: str):
        return getattr(self._base, name)

    def flavor_projection(self, project, selection_id, swarm, work):
        payload = copy.deepcopy(self.payload)
        payload["project"].update(  # type: ignore[union-attr]
            selection_id=selection_id, id=project.name, swarm_id=swarm, work_id=work
        )
        return payload


def unavailable(code: str, message: str) -> dict[str, object]:
    return {"status": "unavailable", "reason": {"code": code, "message": message}}


class BrowserCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if executable is None and Path("/snap/bin/chromium").exists():
            executable = "/snap/bin/chromium"
        cls.browser: Browser = cls.playwright.chromium.launch(
            headless=True, executable_path=executable, args=["--no-sandbox"]
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def open_page(self, studio: RunningStudio, width: int = 1440) -> Page:
        context = self.browser.new_context(viewport={"width": width, "height": 1000})
        self.addCleanup(context.close)
        page = context.new_page()
        self.console_errors: list[str] = []
        self.requests: list[str] = []
        self.bodies: list[str] = []
        page.on(
            "console",
            lambda m: (
                self.console_errors.append(m.text)
                if m.type == "error" and "status of 4" not in m.text and "status of 5" not in m.text
                else None
            ),
        )
        page.on("pageerror", lambda error: self.console_errors.append(str(error)))
        page.on("request", lambda request: self.requests.append(request.url))
        page.on(
            "response",
            lambda response: (
                self.bodies.append(response.text()) if "/api/v1/" in response.url else None
            ),
        )
        page.goto(f"http://127.0.0.1:{studio.port}/")
        return page

    def select_project(self, page: Page, project: Path) -> None:
        page.locator("#project-path").fill(str(project))
        page.get_by_role("button", name="Open", exact=True).click()
        page.get_by_role("heading", name="Process status").wait_for()

    def open_ai_sdlc(self, page: Page) -> None:
        page.get_by_role("button", name="AI-SDLC", exact=True).click()
        page.locator("#ai-sdlc-work-select").select_option("delivery/release")
        page.locator("[data-ai-sdlc-error], .ai-sdlc-grid").first.wait_for()


class FixtureProjectionTests(BrowserCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {"AGORA_HOME": str(self.root / "home")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.project = create_gate_project(self.root)
        self.gateway = FixtureGateway(CoreReadGateway())
        self.studio = RunningStudio(ProjectStore(self.gateway))
        self.addCleanup(self.studio.close)

    def show(self, name: str, width: int = 1440) -> Page:
        self.gateway.payload = load(name)
        page = self.open_page(self.studio, width)
        self.select_project(page, self.project)
        self.open_ai_sdlc(page)
        return page

    def test_complete_projection_renders_every_section_and_blocked_decisions(self) -> None:
        page = self.show("complete")
        for section in (
            "flavor",
            "profiles",
            "lifecycle",
            "clarifications",
            "separation",
            "provenance",
            "metrics",
        ):
            self.assertEqual(
                page.locator(f"[data-section='{section}']").get_attribute("data-status"),
                "available",
                section,
            )
        self.assertEqual(
            page.locator("[data-state-id='construction']").get_attribute("aria-current"), "step"
        )
        self.assertIn(
            "blocked",
            page.locator("[data-transition='construction>operations']").inner_text().lower(),
        )
        self.assertIn(
            "Required quality review is missing",
            page.locator("[data-transition='construction>operations']").inner_text(),
        )
        self.assertEqual(page.locator("[data-decision]").get_attribute("data-decision"), "blocked")
        self.assertIn(
            "Independent review is not recorded",
            page.locator("[data-section='separation']").inner_text(),
        )
        self.assertIn(
            "Which timeout is contractually supported?",
            page.locator("[data-clarification]").inner_text(),
        )
        self.assertIn("observed", page.locator("[data-session='build-session-17']").inner_text())
        self.assertIn("0.1 ratio", page.locator("[data-metric='change-failure-rate']").inner_text())
        self.assertEqual(self.console_errors, [])

    def test_presentation_order_is_only_a_hint_and_labels_are_literal_text(self) -> None:
        self.gateway.payload = load("complete")
        self.gateway.payload["presentation"]["labels"]["construction"] = (
            "<img src=x onerror=window.pwned=1>"  # type: ignore[index]
        )
        self.gateway.payload["presentation"]["labels"]["separation"] = "x" * 200  # type: ignore[index]
        self.gateway.payload["presentation"]["section_order"] = ["metrics", "bogus", "metrics"]  # type: ignore[index]
        page = self.open_page(self.studio)
        self.select_project(page, self.project)
        self.open_ai_sdlc(page)
        order = page.locator("[data-section]").evaluate_all(
            "nodes => nodes.map(n => n.dataset.section)"
        )
        self.assertEqual(order[:3], ["flavor", "profiles", "metrics"])
        self.assertEqual(sorted(order), sorted({*order}))
        self.assertEqual(len(order), 7)
        self.assertEqual(page.locator("[data-state-id='construction'] img").count(), 0)
        self.assertIn("<img src=x", page.locator("[data-state-id='construction']").inner_text())
        self.assertFalse(page.evaluate("Boolean(window.pwned)"))
        self.assertIn("separation", page.locator("[data-section='separation'] h3").inner_text())

    def test_every_unavailable_section_is_explicit_and_independent(self) -> None:
        page = self.show("unavailable")
        cards = page.locator(".ai-sdlc-card.is-unavailable")
        self.assertEqual(cards.count(), 7)
        self.assertIn(
            "projection.metrics-unavailable", page.locator("[data-section='metrics']").inner_text()
        )
        self.assertIn(
            "no core-backed metric window",
            page.locator("[data-section='metrics']").inner_text().lower(),
        )
        self.assertEqual(page.locator("[data-ai-sdlc-error]").count(), 0)
        self.assertEqual(self.console_errors, [])

    def test_future_states_and_sections_render_without_hard_coded_transitions(self) -> None:
        page = self.show("future-state")
        ids = page.locator("[data-state-id]").evaluate_all(
            "nodes => nodes.map(n => n.dataset.stateId)"
        )
        self.assertTrue(ids)
        expected = [state["id"] for state in load("future-state")["lifecycle"]["value"]["states"]]  # type: ignore[index]
        self.assertEqual(ids, expected)
        self.assertEqual(
            page.locator("[data-section='provenance']").get_attribute("data-status"), "unavailable"
        )
        self.assertEqual(
            page.locator("[data-section='lifecycle']").get_attribute("data-status"), "available"
        )
        self.assertEqual(
            page.locator("[data-section='separation']").get_attribute("data-status"), "unavailable"
        )
        self.assertEqual(self.console_errors, [])

    def test_incompatible_aggregates_fail_closed_without_breaking_other_views(self) -> None:
        self.gateway.payload = load("complete")
        self.gateway.payload["schema"] = "agora-ai-sdlc/studio-projection/v2"
        page = self.open_page(self.studio)
        self.select_project(page, self.project)
        self.open_ai_sdlc(page)
        alert = page.locator("[data-ai-sdlc-error]")
        self.assertIn("supports agora-ai-sdlc/studio-projection/v1", alert.inner_text())
        self.assertEqual(page.locator(".ai-sdlc-card").count(), 0)
        page.get_by_role("button", name="Work", exact=True).click()
        page.get_by_role("heading", name="Work control").wait_for()

    def test_requests_and_responses_never_carry_filesystem_paths_or_secrets(self) -> None:
        self.show("complete")
        projection_requests = [url for url in self.requests if "/ai-sdlc/projection" in url]
        self.assertTrue(projection_requests)
        for url in projection_requests:
            self.assertNotIn(str(self.project), url)
            self.assertNotIn(self.project.name, url.split("?", 1)[1].split("selection=")[0])
            self.assertIn("selection=selected-", url)
        projection_bodies = [
            body for body in self.bodies if '"agora-studio/api/ai-sdlc-projection/v1"' in body
        ]
        self.assertTrue(projection_bodies)
        for body in projection_bodies:
            self.assertNotIn(str(self.project), body)
            self.assertNotIn("csrf", body.lower())
            self.assertNotIn("PRIVATE KEY", body)

    def test_narrow_viewport_has_no_horizontal_overflow_and_keeps_controls_reachable(self) -> None:
        page = self.show("complete", width=390)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
        self.assertTrue(page.locator("#ai-sdlc-work-select").is_visible())
        self.assertTrue(page.locator("#refresh-button").is_visible())

    def test_semantic_structure_is_accessible(self) -> None:
        page = self.show("complete")
        labelled = page.locator(".ai-sdlc-card").evaluate_all(
            "cards => cards.every(card => { const id = card.getAttribute('aria-labelledby'); return id && document.getElementById(id)?.textContent.trim(); })"
        )
        self.assertTrue(labelled)
        self.assertEqual(page.locator("ol[aria-label='Lifecycle states']").count(), 1)
        self.assertTrue(page.get_by_label("Work item").is_visible())
        page.keyboard.press("Tab")
        self.assertTrue(page.evaluate("document.activeElement !== document.body"))


class ProjectionStub:
    """A provider-neutral projector that derives its answer from the Core-supplied context."""

    projection_schema = "agora-ai-sdlc/studio-projection/v1"
    projection_schema_document = json.loads((FIXTURES / "schema.json").read_text(encoding="utf-8"))
    required_sections = ("flavor", "profiles", "provenance", "separation", "metrics")

    def project(self, context) -> FlavorProjectionContribution:
        approvals = len(context.work.approvals)
        return FlavorProjectionContribution(
            sections={
                "flavor": unavailable("projection.flavor-unavailable", "No flavor"),
                "profiles": unavailable("projection.profiles-unavailable", "No profile"),
                "provenance": unavailable("projection.provenance-unavailable", "None"),
                "separation": {
                    "status": "available",
                    "value": {
                        "source_schema": "agora-ai-sdlc/independent-review/v1",
                        "decision": "blocked" if approvals == 0 else "satisfied",
                        "required_dimensions": ["actor"],
                        "blockers": [
                            {"code": "review.missing", "message": "Independent review is missing"}
                        ]
                        if approvals == 0
                        else [],
                    },
                },
                "metrics": unavailable("projection.metrics-unavailable", "No metrics"),
            },
            presentation={"authoritative": False, "labels": {}, "section_order": []},
        )


class RealCoreProjectionTests(BrowserCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {"AGORA_HOME": str(self.root / "home")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.project = create_gate_project(self.root)
        store = ProjectStore(CoreReadGateway(flavor_projectors=(ProjectionStub(),)))
        self.studio = RunningStudio(store)
        self.addCleanup(self.studio.close)

    def test_real_core_blocked_gate_and_stale_refresh(self) -> None:
        page = self.open_page(self.studio)
        self.select_project(page, self.project)
        self.open_ai_sdlc(page)
        self.assertEqual(page.locator("[data-decision]").get_attribute("data-decision"), "blocked")
        before = page.locator("[data-snapshot]").get_attribute("data-snapshot")
        current = page.locator("[data-state-id][aria-current='step']").get_attribute(
            "data-state-id"
        )
        self.assertEqual(current, "verifying")

        AgoraWorkspace(cwd=self.project).transition_work(
            TransitionWorkInput(
                swarm_id="delivery",
                work_id="release",
                actor_id="developer",
                target_state="implementing",
            )
        )
        page.get_by_role("button", name="Refresh").click()
        page.locator("[data-ai-sdlc-notice]").wait_for()
        after = page.locator("[data-snapshot]").get_attribute("data-snapshot")
        self.assertNotEqual(before, after)
        self.assertEqual(
            page.locator("[data-state-id][aria-current='step']").get_attribute("data-state-id"),
            "implementing",
        )
        self.assertEqual(self.console_errors, [])

    def test_refresh_failure_keeps_the_last_verified_view(self) -> None:
        page = self.open_page(self.studio)
        self.select_project(page, self.project)
        self.open_ai_sdlc(page)
        page.route(
            "**/api/v1/ai-sdlc/projection*",
            lambda route: route.fulfill(
                status=502,
                content_type="application/json",
                body=json.dumps(
                    {
                        "schema": "agora-studio/api/error/v1",
                        "error": "read.invalid-durable-state",
                        "reason": "Core could not read the project",
                    }
                ),
            ),
        )
        page.get_by_role("button", name="Refresh").click()
        page.locator(".inline-error").wait_for()
        self.assertIn(
            "last verified view is still shown", page.locator(".inline-error").inner_text()
        )
        self.assertGreater(page.locator(".ai-sdlc-card").count(), 0)


if __name__ == "__main__":
    unittest.main()
