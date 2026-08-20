from __future__ import annotations

import base64
import hashlib
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agora.model import AddArtifactInput, CreateWorkInput
from agora.workspace import AgoraWorkspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

try:
    from .support import (
        RunningStudio,
        add_multiple_gate_options,
        add_specification_history,
        create_gate_project,
    )
except ImportError:  # Direct execution from an installed-wheel verification directory.
    from support import (
        RunningStudio,
        add_multiple_gate_options,
        add_specification_history,
        create_gate_project,
    )


class ChromiumControlPlaneTests(unittest.TestCase):
    """Exercise the shipped browser assets against real Core and Studio wheels/source."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if executable is None and Path("/snap/bin/chromium").exists():
            executable = "/snap/bin/chromium"
        cls.browser: Browser = cls.playwright.chromium.launch(
            headless=True,
            executable_path=executable,
            args=["--no-sandbox"],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {"AGORA_HOME": str(self.root / "home")})
        self.environment.start()
        self.project = create_gate_project(self.root)
        self.studio = RunningStudio()
        self.context: BrowserContext = self.browser.new_context(
            viewport={"width": 1440, "height": 1000}
        )
        self.context.grant_permissions(["clipboard-read", "clipboard-write"])
        self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self.page: Page = self.context.new_page()
        self.console_errors: list[str] = []
        self.page.on(
            "console",
            lambda message: (
                self.console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        self.page.on("pageerror", lambda error: self.console_errors.append(str(error)))
        self.page.goto(f"http://127.0.0.1:{self.studio.port}/")

    def tearDown(self) -> None:
        result = self._outcome.result
        failed = any(test is self for test, _ in [*result.failures, *result.errors])
        if failed:
            artifact_root = Path(os.environ.get("E2E_ARTIFACT_DIR", "test-results/e2e"))
            artifact_root.mkdir(parents=True, exist_ok=True)
            stem = self.id().rsplit(".", 1)[-1]
            self.page.screenshot(path=str(artifact_root / f"{stem}.png"), full_page=True)
            self.context.tracing.stop(path=artifact_root / f"{stem}.zip")
        else:
            self.context.tracing.stop()
        self.context.close()
        self.studio.close()
        self.environment.stop()
        self.temporary.cleanup()

    def select(self, project: Path | None = None) -> None:
        selected = project or self.project
        self.page.locator("#project-path").fill(str(selected))
        self.page.get_by_role("button", name="Open", exact=True).click()
        self.page.get_by_role("heading", name="Process status").wait_for()
        self.page.wait_for_function(
            "name => document.querySelector('#selected-project-name')?.textContent === name",
            arg=selected.name,
        )

    def open_approvals(self) -> None:
        self.page.get_by_role("button", name="Work", exact=True).click()
        self.page.get_by_role("button", name="Open work item Release safely").click()
        self.page.get_by_role("tab", name="Approvals").click()
        self.page.get_by_role("heading", name="Core decision options").wait_for()

    def prepare(self, *, decision: str = "approved", reason: str = "Evidence reviewed") -> None:
        self.page.locator(
            f".gate-option:not(.is-disabled):has-text('{decision.capitalize()}') input"
        ).first.check()
        self.page.locator("#gate-reason").fill(reason)
        self.page.get_by_role("button", name="Prepare exact action").click()
        self.page.locator("#canonical-payload").wait_for()

    def enable_signed_owner(self) -> Ed25519PrivateKey:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        fingerprint = hashlib.sha256(public_key).hexdigest()
        original_find = AgoraWorkspace._find_actor

        def authenticated_owner(workspace, project_root, actor_id):
            actor = original_find(workspace, project_root, actor_id)
            if actor.reference != "project:owner":
                return actor
            return replace(
                actor,
                authentication_required=True,
                authentication_algorithm="ed25519",
                authentication_public_key=base64.b64encode(public_key).decode("ascii"),
                authentication_fingerprint=fingerprint,
            )

        find_patch = patch.object(AgoraWorkspace, "_find_actor", authenticated_owner)
        key_patch = patch.object(AgoraWorkspace, "_assert_current_actor_key", lambda *args: None)
        find_patch.start()
        key_patch.start()
        self.addCleanup(key_patch.stop)
        self.addCleanup(find_patch.stop)
        return private_key

    def test_01_selects_a_real_local_project(self) -> None:
        self.select()
        self.assertEqual(
            self.page.locator("#selected-project-name").inner_text(), "governed-project"
        )

    def test_02_opens_work_detail_from_the_board(self) -> None:
        self.select()
        self.open_approvals()
        self.assertTrue(self.page.get_by_role("tab", name="Summary").is_visible())

    def test_03_renders_multiple_core_gate_options(self) -> None:
        add_multiple_gate_options(self.project)
        self.select()
        self.open_approvals()
        self.assertEqual(self.page.locator(".gate-option").count(), 6)

    def test_04_disables_a_core_blocked_option(self) -> None:
        blocked = create_gate_project(self.root, include_evidence=False, name="blocked-project")
        self.select(blocked)
        self.open_approvals()
        self.assertGreater(self.page.locator(".gate-option.is-disabled").count(), 0)
        self.assertTrue(self.page.locator(".gate-option.is-disabled input").first.is_disabled())

    def test_05_prepares_an_approval_through_core(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare()
        self.page.get_by_text("Confirm governed mutation").wait_for()

    def test_06_unsigned_preparation_reaches_confirmation(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare()
        self.assertTrue(self.page.get_by_role("button", name="Confirm approved").is_enabled())
        self.assertEqual(self.page.locator("#detached-signature").count(), 0)

    def test_07_displays_and_copies_the_exact_canonical_payload(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare(reason="  Evidence   reviewed  ")
        payload = self.page.locator("#canonical-payload").input_value()
        self.assertIn('"reason":"Evidence reviewed"', payload)
        self.page.get_by_role("button", name="Copy canonical payload").click()
        self.assertEqual(self.page.evaluate("navigator.clipboard.readText()"), payload)

    def test_08_shows_the_opaque_precondition_digest(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare()
        text = self.page.locator(".gate-confirmation").inner_text()
        self.assertIn("PRECONDITION DIGEST", text)
        self.assertRegex(text, r"[0-9a-f]{64}")

    def test_09_groups_evidence_references_by_core_type(self) -> None:
        self.select()
        self.open_approvals()
        typed = self.page.locator(".typed-evidence").first.inner_text()
        self.assertIn("test-run", typed)
        self.assertIn("repo://reports/release.txt", typed)

    def test_10_persists_approval_then_refreshes_activity(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare()
        self.page.get_by_role("button", name="Confirm approved").click()
        self.page.locator(".gate-control").get_by_text(
            "Approval was durably persisted by Agora Core.", exact=True
        ).wait_for()
        self.page.get_by_role("tab", name="Activity").click()
        self.page.get_by_text("approval.added", exact=True).wait_for()

    def test_11_persists_a_durable_rejection(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare(decision="rejected", reason="Return to implementation")
        self.page.get_by_role("button", name="Confirm rejected").click()
        self.page.get_by_text("Rejection was durably persisted by Agora Core.").wait_for()
        self.page.get_by_role("tab", name="Activity").click()
        self.page.get_by_text("gate.rejected", exact=True).wait_for()

    def test_12_stale_material_forces_refresh_and_reprepare(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare()
        extra = self.project / "reports" / "late.txt"
        extra.write_text("late durable material\n", encoding="utf-8")
        AgoraWorkspace(cwd=self.project).add_artifact(
            AddArtifactInput(
                swarm_id="delivery",
                work_id="release",
                actor_id="developer",
                kind="late-report",
                uri="repo://reports/late.txt",
            )
        )
        self.page.get_by_role("button", name="Confirm approved").click()
        self.page.locator(
            ".notice-error span", has_text="The work state changed after this view loaded."
        ).wait_for()
        self.assertEqual(self.page.locator("#canonical-payload").count(), 0)

    def test_13_latest_project_selection_wins(self) -> None:
        second = create_gate_project(self.root, name="second-project")
        self.select()
        self.select(second)
        self.assertEqual(self.page.locator("#selected-project-name").inner_text(), "second-project")

    def test_13_rapid_revision_selection_keeps_the_latest_response(self) -> None:
        add_specification_history(self.project)
        self.select()
        self.page.get_by_role("button", name="Work", exact=True).click()
        self.page.get_by_role("button", name="Open work item Release safely").click()
        self.page.get_by_role("tab", name="Spec").click()
        revisions = self.page.locator(".revision-button")
        revisions.first.wait_for()
        self.assertGreaterEqual(revisions.count(), 2)
        revisions.nth(0).click()
        expected_subject = revisions.nth(1).locator("span").first.inner_text()
        revisions.nth(1).click()
        detail = self.page.locator("#revision-detail-title")
        detail.wait_for()
        self.assertEqual(detail.inner_text(), expected_subject)
        self.assertTrue(revisions.nth(1).get_attribute("aria-current") == "true")

    def test_14_old_control_response_is_cancelled_on_project_change(self) -> None:
        second = create_gate_project(self.root, name="newer-project")
        self.select()
        self.page.get_by_role("button", name="Work", exact=True).click()
        self.page.get_by_role("button", name="Open work item Release safely").click()
        self.select(second)
        self.assertEqual(self.page.locator("#selected-project-name").inner_text(), "newer-project")
        self.assertNotIn(
            str(self.project), self.page.locator("#selected-project-name").inner_text()
        )

    def test_15_tabs_are_keyboard_navigable(self) -> None:
        self.select()
        self.open_approvals()
        tab = self.page.get_by_role("tab", name="Approvals")
        tab.focus()
        tab.press("ArrowRight")
        self.assertEqual(self.page.locator(":focus").get_attribute("data-tab"), "activity")
        self.page.locator(":focus").press("Home")
        self.assertEqual(self.page.locator(":focus").get_attribute("data-tab"), "summary")

    def test_16_validation_error_returns_focus_to_reason(self) -> None:
        self.select()
        self.open_approvals()
        self.page.locator(".gate-option:not(.is-disabled) input").first.check()
        self.page.get_by_role("button", name="Prepare exact action").click()
        self.page.get_by_text("A reason is required for every gate decision.").wait_for()
        self.assertEqual(self.page.locator(":focus").get_attribute("id"), "gate-reason")

    def test_17_has_no_browser_console_or_page_errors(self) -> None:
        self.select()
        self.open_approvals()
        self.prepare()
        self.assertEqual(self.console_errors, [])

    def test_18_durable_text_is_never_interpreted_as_html(self) -> None:
        AgoraWorkspace(cwd=self.project).create_work(
            CreateWorkInput(
                swarm_id="delivery",
                id="unsafe-title",
                title='<img src="x" onerror="globalThis.injected=true">',
                actor_id="owner",
            )
        )
        self.select()
        self.page.get_by_role("button", name="Work", exact=True).click()
        self.page.get_by_text('<img src="x" onerror="globalThis.injected=true">').wait_for()
        self.assertEqual(self.page.locator('img[src="x"]').count(), 0)
        self.assertIsNone(self.page.evaluate("globalThis.injected"))

    def test_19_signed_actor_receives_core_authentication_metadata(self) -> None:
        self.enable_signed_owner()
        self.select()
        self.open_approvals()
        self.prepare()
        self.page.get_by_text("Detached signature required").wait_for()
        self.assertEqual(self.page.locator("#signature-algorithm").input_value(), "ed25519")
        self.assertRegex(
            self.page.locator("#signature-fingerprint").input_value(), r"^[0-9a-f]{64}$"
        )

    def test_20_detached_signature_is_persisted_without_optimism(self) -> None:
        private_key = self.enable_signed_owner()
        self.select()
        self.open_approvals()
        self.prepare()
        payload = self.page.locator("#canonical-payload").input_value().encode("ascii")
        signature = base64.b64encode(private_key.sign(payload)).decode("ascii")
        self.page.locator("#detached-signature").fill(signature)
        self.page.get_by_role("button", name="Confirm approved").click()
        self.page.locator(".gate-control").get_by_text(
            "Approval was durably persisted by Agora Core.", exact=True
        ).wait_for()

    def test_21_mobile_view_keeps_primary_controls_operable(self) -> None:
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.select()
        self.page.get_by_role("button", name="Work", exact=True).click()
        self.assertTrue(self.page.locator("#main-content").is_visible())
        self.assertTrue(
            self.page.get_by_role("button", name="Open work item Release safely").is_visible()
        )


if __name__ == "__main__":
    unittest.main()
