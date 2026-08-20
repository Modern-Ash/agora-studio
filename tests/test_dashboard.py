from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from agora_studio.core import AgoraCliBoundary, ProjectStore
from agora_studio.server import handle_api, static_response
from tests.test_foundation import make_project
from tests.test_visual_console import OverviewRunner


class DashboardModelTests(unittest.TestCase):
    static = Path(__file__).parents[1] / "agora_studio" / "static"

    def test_dashboard_model_derives_process_metrics_board_and_assignment(self) -> None:
        model = self.static / "dashboard-model.js"
        script = f"""
require({json.dumps(str(model))});
const overview = {{
  swarms: [
    {{id:'delivery', status:'running', assignments:{{developer:'project:agent'}}}},
    {{id:'archive', status:'completed', assignments:{{}}}},
  ],
  work: [
    {{id:'build', swarm_id:'delivery', state:'implementing', operational_status:'active', evidence_results:[]}},
    {{id:'review', swarm_id:'delivery', state:'verifying', operational_status:'blocked', evidence_results:['success']}},
    {{id:'done', swarm_id:'archive', state:'completed', operational_status:'active', evidence_results:['success']}},
  ],
  sessions: [{{status:'failed'}}, {{status:'completed'}}],
}};
const details = {{
  'delivery/build': {{
    lifecycle: {{method: {{current_state:'implementing', states:[{{id:'drafting'}},{{id:'implementing'}},{{id:'verifying'}},{{id:'completed'}}], transitions:[{{from:'implementing',to:'verifying',gate:'quality',blockers:['successful evidence required']}}]}}}},
    artifacts: {{approvals: {{satisfaction:[{{role:'owner',satisfied:false}}]}}}},
  }},
}};
const metrics = DashboardModel.metrics(overview, details);
const columns = DashboardModel.boardColumns(overview.work, details);
const assignment = DashboardModel.assignmentFor(overview.work[0], overview.swarms);
const gates = DashboardModel.pendingGates(details['delivery/build'].lifecycle);
const recent = DashboardModel.recentActivity([{{timestamp:'2026-01-01'}},{{timestamp:'2026-01-03'}},{{timestamp:'2026-01-02'}}], 2);
process.stdout.write(JSON.stringify({{metrics, states:columns.map((item)=>item.state), assignment, gates, recent:recent.map((item)=>item.timestamp)}}));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)

        self.assertEqual(
            {
                "activeSwarms": 1,
                "workInProgress": 2,
                "blockedWork": 1,
                "pendingApprovals": 1,
                "missingEvidence": 1,
                "failedSessions": 1,
            },
            output["metrics"],
        )
        self.assertEqual(["drafting", "implementing", "verifying", "completed"], output["states"])
        self.assertEqual(
            {"role": "developer", "actor": "project:agent", "additional": 0},
            output["assignment"],
        )
        self.assertEqual("quality", output["gates"][0]["id"])
        self.assertEqual(["2026-01-03", "2026-01-02"], output["recent"])

    def test_dashboard_model_is_a_packaged_static_asset(self) -> None:
        body, content_type, cache = static_response("/assets/dashboard-model.js")

        self.assertEqual("text/javascript; charset=utf-8", content_type)
        self.assertTrue(cache)
        self.assertIn(b"DashboardModel", body)

    def test_dashboard_exposes_required_navigation_metrics_tabs_and_states(self) -> None:
        html = (self.static / "index.html").read_text(encoding="utf-8")
        javascript = (self.static / "app.js").read_text(encoding="utf-8")
        css = (self.static / "styles.css").read_text(encoding="utf-8")

        self.assertEqual(
            ["overview", "work", "swarms", "actors", "activity"],
            [
                value.split('data-view="', 1)[1].split('"', 1)[0]
                for value in html.splitlines()
                if "data-view=" in value
            ],
        )
        for label in (
            "Active Method Pack",
            "Active swarms",
            "Work in progress",
            "Blocked",
            "Pending approvals",
            "Evidence missing",
            "Failed sessions",
            "Recent activity",
        ):
            self.assertIn(label, javascript)
        for tab in (
            "summary",
            "spec",
            "lifecycle",
            "artifacts",
            "evidence",
            "approvals",
            "activity",
        ):
            self.assertIn(f'"{tab}"', javascript)
        for state_contract in (
            "loadingRows",
            "emptyState",
            "notice-error",
            "notice-partial",
        ):
            self.assertIn(state_contract, f"{javascript}\n{css}")
        self.assertIn('role: "tablist"', javascript)
        self.assertIn("ArrowRight", javascript)
        self.assertIn(":focus-visible", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)


class VersionedRouteTests(unittest.TestCase):
    def test_v1_routes_preserve_read_contracts(self) -> None:
        store = ProjectStore()

        self.assertEqual(200, handle_api(store, "GET", "/api/v1/project")[0])
        for route in (
            "/api/v1/overview",
            "/api/v1/activity",
            "/api/v1/lifecycle",
            "/api/v1/artifacts",
        ):
            with self.subTest(route=route):
                self.assertEqual(409, handle_api(store, "GET", route)[0])
        self.assertEqual(404, handle_api(store, "GET", "/api/v1/unknown")[0])

    def test_v1_selection_and_overview_use_existing_read_only_services(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory), "visual-test")
            runner = OverviewRunner()
            store = ProjectStore(AgoraCliBoundary(runner=runner))

            selected_status, selected = handle_api(
                store, "POST", "/api/v1/projects/select", {"path": str(project)}
            )
            overview_status, overview = handle_api(store, "GET", "/api/v1/overview")

        self.assertEqual(200, selected_status)
        self.assertEqual("visual-test", selected["project"]["project"])
        self.assertEqual(200, overview_status)
        self.assertEqual("spec-driven", overview["status"]["default_method"])
        self.assertEqual("work", overview["work"][0]["id"])


if __name__ == "__main__":
    unittest.main()
