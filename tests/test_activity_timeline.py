from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from agora_studio.core import AgoraCliBoundary, ProjectStore
from agora_studio.server import handle_api, static_response
from tests.test_foundation import make_project


def event(**overrides: str | None) -> dict[str, str | None]:
    record: dict[str, str | None] = {
        "timestamp": "2026-08-17T12:00:00Z",
        "type": "work.transitioned",
        "summary": "from=planned to=implementing",
        "actor": "project:agent",
        "swarm_id": "studio",
        "work_id": "timeline",
        "session_id": None,
        "tool_run_id": None,
        "source": "repo://.agora/events.md",
        "path": "/private/project/.agora/activity.md",
    }
    record.update(overrides)
    return record


class ActivityRunner:
    def __init__(self, events: object | None = None, returncode: int = 0, stderr: str = "") -> None:
        self.events = [event()] if events is None else events
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        if command[-1] == "status":
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"project": "activity-test"}), ""
            )
        stdout = json.dumps(self.events) if self.returncode == 0 else ""
        return subprocess.CompletedProcess(command, self.returncode, stdout, self.stderr)


class ActivityBoundaryTests(unittest.TestCase):
    def test_exact_allowlisted_argv_and_process_bounds(self) -> None:
        runner = ActivityRunner()
        boundary = AgoraCliBoundary(runner=runner, timeout_seconds=3.5)
        store = ProjectStore(boundary)
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory), "activity-test")
            store.select(str(project))
            runner.calls.clear()
            result = store.activity(
                {
                    "type": "work.transitioned",
                    "actor": "project:agent",
                    "swarm": "studio",
                    "work": "timeline",
                    "session": "run-1",
                    "tool_run": "tool-1",
                    "limit": "25",
                }
            )

        command, kwargs = runner.calls[0]
        self.assertEqual(
            [
                "agora",
                "--project",
                str(project.resolve()),
                "activity",
                "list",
                "--type",
                "work.transitioned",
                "--actor",
                "project:agent",
                "--swarm",
                "studio",
                "--work",
                "timeline",
                "--session",
                "run-1",
                "--tool-run",
                "tool-1",
                "--limit",
                "25",
            ],
            command,
        )
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(3.5, kwargs["timeout"])
        self.assertEqual(1, result["meta"]["count"])
        self.assertEqual(25, result["meta"]["limit"])

    def test_invalid_queries_never_launch_activity(self) -> None:
        invalid_queries = [
            {"rebuild": "true"},
            {"actor": ["one", "two"]},
            {"actor": "bad\nactor"},
            {"work": "x" * 201},
            {"limit": "0"},
            {"limit": "501"},
            {"limit": "many"},
        ]
        for query in invalid_queries:
            with self.subTest(query=query), tempfile.TemporaryDirectory() as directory:
                runner = ActivityRunner()
                store = ProjectStore(AgoraCliBoundary(runner=runner))
                store.select(str(make_project(Path(directory), "activity-test")))
                runner.calls.clear()

                status, payload = handle_api(store, "GET", "/api/activity", query=query)

                self.assertEqual(400, status)
                self.assertEqual("invalid_activity_query", payload["error"])
                self.assertEqual([], runner.calls)

    def test_json_shape_and_field_types_are_enforced(self) -> None:
        invalid_results = [
            {"events": []},
            [{"timestamp": "2026-08-17T12:00:00Z"}],
            [event(actor=42)],
        ]
        for result in invalid_results:
            with self.subTest(result=result), tempfile.TemporaryDirectory() as directory:
                runner = ActivityRunner(events=result)
                store = ProjectStore(AgoraCliBoundary(runner=runner))
                store.select(str(make_project(Path(directory), "activity-test")))

                status, payload = handle_api(store, "GET", "/api/activity")

                self.assertEqual(502, status)
                self.assertEqual("activity_query_failed", payload["error"])
                self.assertEqual("activity", payload["operation"])


class ActivityApiTests(unittest.TestCase):
    def test_selection_is_required_and_success_is_normalized(self) -> None:
        status, payload = handle_api(ProjectStore(), "GET", "/api/activity")
        self.assertEqual(409, status)
        self.assertEqual("project_required", payload["error"])

        records = [event(), event(timestamp="2026-08-17T12:01:00Z", actor=None)]
        with tempfile.TemporaryDirectory() as directory:
            runner = ActivityRunner(records)
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            selected = store.select(str(make_project(Path(directory), "activity-test")))
            status, payload = handle_api(
                store, "GET", "/api/activity", query={"actor": "All", "limit": "2"}
            )

        self.assertEqual(200, status)
        self.assertEqual(selected.as_dict(), payload["selection"])
        self.assertIsNone(payload["filters"]["actor"])
        self.assertEqual(records, payload["events"])
        self.assertEqual({"count": 2, "limit": 2, "limit_reached": True}, payload["meta"])

    def test_cli_failure_is_safe_and_preserves_selection(self) -> None:
        secret = "PRIVATE_KEY=do-not-return"
        with tempfile.TemporaryDirectory() as directory:
            runner = ActivityRunner(returncode=7, stderr=secret)
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            selected = store.select(str(make_project(Path(directory), "activity-test")))

            status, payload = handle_api(store, "GET", "/api/activity")

        self.assertEqual(502, status)
        self.assertEqual("activity_query_failed", payload["error"])
        self.assertNotIn(secret, json.dumps(payload))
        self.assertEqual(selected, store.selection)

    def test_activity_read_does_not_mutate_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory), "activity-test")
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            runner = ActivityRunner([event()])
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            store.select(str(project))
            before = self._snapshot(project)
            before_git = self._git_status(project)

            status, _ = handle_api(store, "GET", "/api/activity")

            self.assertEqual(200, status)
            self.assertEqual(before, self._snapshot(project))
            self.assertEqual(before_git, self._git_status(project))

    @staticmethod
    def _snapshot(project: Path) -> dict[str, str]:
        return {
            str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(project.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(project).parts
        }

    @staticmethod
    def _git_status(project: Path) -> str:
        return subprocess.run(
            ["git", "-C", str(project), "status", "--porcelain=v1"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout


class ActivityUiContractTests(unittest.TestCase):
    static = Path(__file__).parents[1] / "agora_studio" / "static"

    def test_activity_model_orders_filters_and_matches_exact_relationships(self) -> None:
        model = self.static / "activity-model.js"
        fixture = [
            event(timestamp="2026-08-17T12:02:00Z", type="evidence.added", summary="right"),
            event(timestamp="2026-08-17T12:01:00Z", actor="project:owner", summary="oldest"),
            event(timestamp="2026-08-17T12:02:00Z", type="artifact.added", summary="tie second"),
            event(
                timestamp="2026-08-17T12:03:00Z",
                work_id="other",
                type="evidence.added",
                summary="wrong work",
            ),
        ]
        script = f"""
require({json.dumps(str(model))});
const events = {json.dumps(fixture)};
const ordered = ActivityModel.sortChronologically(events);
const filtered = ActivityModel.filterEvents(events, {{actor: 'project:agent', work_id: 'timeline'}});
const related = ActivityModel.relatedWork(events, events[0]);
process.stdout.write(JSON.stringify({{
  order: ordered.map((item) => item.summary),
  filtered: filtered.length,
  related: related.map((item) => item.summary),
  missingSession: ActivityModel.matchingSession([], {{session_id: 'none'}}),
}}));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        self.assertEqual(["oldest", "right", "tie second", "wrong work"], output["order"])
        self.assertEqual(2, output["filtered"])
        self.assertEqual(["right", "tie second"], output["related"])
        self.assertIsNone(output["missingSession"])

    def test_activity_assets_and_accessibility_contracts_are_present(self) -> None:
        html = (self.static / "index.html").read_text(encoding="utf-8")
        javascript = (self.static / "app.js").read_text(encoding="utf-8")
        css = (self.static / "styles.css").read_text(encoding="utf-8")
        body, content_type, cache = static_response("/assets/activity-model.js")

        self.assertEqual("text/javascript; charset=utf-8", content_type)
        self.assertTrue(cache)
        self.assertTrue(body)
        self.assertIn('data-view="activity"', html)
        for contract in (
            "activityFilters",
            "renderActivity",
            "ActivityModel.filterEvents",
            "ActivityModel.options",
            "activityLoading",
            "emptyState",
            "loadingRows",
            "activityError",
        ):
            self.assertIn(contract, javascript)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("grid-template-columns: repeat(3, minmax(160px, 1fr)) auto", css)
        self.assertIn("@media (max-width: 460px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertNotIn("innerHTML", javascript)


if __name__ == "__main__":
    unittest.main()
