from __future__ import annotations

import subprocess
import unittest
from importlib.resources import files
from pathlib import Path

import agora_studio
from agora_studio.__main__ import build_parser
from agora_studio.server import static_response

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "agora_studio"


class PackagingTests(unittest.TestCase):
    def test_version_and_core_dependency_are_explicit(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(agora_studio.__version__, "0.4.0")
        self.assertEqual(build_parser().parse_args(["--port", "7358"]).port, 7358)
        self.assertIn('dependencies = ["agora-framework>=0.7,<0.8"]', pyproject)
        self.assertIn('version = { attr = "agora_studio.__version__" }', pyproject)

    def test_static_assets_are_packaged_and_exactly_allowlisted(self) -> None:
        package = files("agora_studio") / "static"
        for name in (
            "index.html",
            "styles.css",
            "app.js",
            "dashboard-model.js",
            "control-model.js",
            "agora-mark.png",
        ):
            self.assertTrue((package / name).is_file())
        self.assertIsNotNone(static_response("/"))
        self.assertIsNone(static_response("/assets/../README.md"))


class FrontendContractTests(unittest.TestCase):
    def test_frontend_uses_only_v1_and_attaches_csrf_to_mutations(self) -> None:
        app = (PACKAGE / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('const API_ROOT = "/api/v1"', app)
        self.assertIn('"X-Agora-Studio-CSRF": state.csrfToken', app)
        self.assertIn("payload.csrf_token", app)
        self.assertNotIn("/api/lifecycle", app)
        self.assertNotIn("/api/overview", app)
        self.assertNotIn("innerHTML", app)

    def test_semantic_accessible_and_local_only_shell(self) -> None:
        html = (PACKAGE / "static" / "index.html").read_text(encoding="utf-8")
        css = (PACKAGE / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("<main", html)
        self.assertIn("<nav", html)
        self.assertIn("skip-link", html)
        self.assertIn(":focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotIn("https://", html)

    def test_javascript_models_parse_without_a_frontend_toolchain(self) -> None:
        for path in (PACKAGE / "static").glob("*.js"):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["node", "--check", str(path)], capture_output=True, text=True, check=False
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_dashboard_consumes_core_attention_and_decision_options(self) -> None:
        model = PACKAGE / "static" / "dashboard-model.js"
        script = f"""
          require({str(model)!r});
          const work = {{swarm_id: 'delivery', id: 'release', state: 'verifying'}};
          const overview = {{status: {{swarm_statuses: {{active: 1}}, attention: {{
            'active-work': ['delivery/release'], 'blocked-work': [], 'failed-sessions': []
          }}}}}};
          const options = [
            {{transition_source: 'verifying', transition_target: 'completed', gate_id: 'completion',
              decision: 'approved', role_id: 'product-owner', actor_id: 'project:owner', allowed: true,
              blockers: [], evidence_references: ['repo://report'],
              evidence_references_by_type: {{'test-run': ['repo://report']}}}},
            {{transition_source: 'verifying', transition_target: 'reviewing', gate_id: 'review',
              decision: 'rejected', role_id: 'scrum-master', actor_id: 'project:facilitator', allowed: false,
              blockers: [{{category: 'evidence', message: 'Evidence missing'}}], evidence_references: [],
              evidence_references_by_type: {{}}}},
            {{transition_source: 'verifying', transition_target: 'completed', gate_id: 'completion',
              decision: 'approved', role_id: 'release-manager', actor_id: 'project:release', allowed: true,
              blockers: [], evidence_references: ['repo://report'],
              evidence_references_by_type: {{'test-run': ['repo://report']}}}},
            {{transition_source: 'verifying', transition_target: 'completed', gate_id: 'completion',
              decision: 'rejected', role_id: 'product-owner', actor_id: 'project:owner', allowed: true,
              blockers: [], evidence_references: [], evidence_references_by_type: {{}}}}
          ];
          const detail = {{control: {{gate_decision_options: {{options}}, lifecycle: {{states: [
            {{id: 'verifying'}}, {{id: 'completed'}}
          ]}}}}}};
          if (!DashboardModel.isWorkInProgress(work, overview)) process.exit(1);
          if (DashboardModel.decisionOptions(detail).length !== 4) process.exit(2);
          if (DashboardModel.gateCount(detail) !== 2) process.exit(3);
          if (!DashboardModel.hasEvidenceBlocker(detail)) process.exit(4);
          if (DashboardModel.findOption(detail, DashboardModel.optionKey(options[1])) !== options[1]) process.exit(5);
          if (DashboardModel.metrics(overview, {{'delivery/release': detail}}).pendingApprovals !== 2) process.exit(6);
          if (new Set(options.map(DashboardModel.optionKey)).size !== 4) process.exit(7);
          const columns = DashboardModel.boardColumns([work, {{...work, id: 'second', state: 'completed'}}],
            {{'delivery/release': detail}});
          if (columns.map((column) => column.state).join(',') !== 'verifying,completed') process.exit(8);
          const assignments = DashboardModel.swarmAssignments(work, [{{id: 'delivery', assignments: {{
            'product-owner': 'project:owner', 'release-manager': 'project:release'
          }}}}]);
          if (assignments.length !== 2) process.exit(9);
        """
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

        source = model.read_text(encoding="utf-8")
        for removed in (
            "pendingGates",
            "gateDecisionContext",
            "currentTransitions",
            "ready: Boolean",
        ):
            self.assertNotIn(removed, source)

    def test_control_model_covers_tabs_signatures_and_exact_commands(self) -> None:
        model = PACKAGE / "static" / "control-model.js"
        script = f"""
          require({str(model)!r});
          const option = {{gate_id: 'completion', actor_id: 'project:owner', decision: 'approved',
            expected_state: 'verifying', transition_target: 'completed', role_id: 'product-owner',
            evidence_references: ['repo://report']}};
          const command = ControlModel.command(option, '  reviewed  ');
          if (command.schema !== 'agora/application/approve-gate-command/v3') process.exit(1);
          if (command.reason !== '  reviewed  ' || command.role_id !== 'product-owner') process.exit(2);
          if (command.precondition_digest !== null) process.exit(13);
          if (ControlModel.nextTab('summary', 'ArrowLeft') !== 'activity') process.exit(3);
          const prepared = {{authentication_required: true}};
          if (!ControlModel.authenticationIssue(prepared, {{algorithm: 'ed25519', fingerprint: '', signature: ''}})) process.exit(4);
          const auth = {{algorithm: 'ed25519', fingerprint: 'a'.repeat(64), signature: 'signed'}};
          if (ControlModel.authenticationIssue(prepared, auth)) process.exit(5);
          if (ControlModel.revisionToken('/one', 'delivery/release', 'working-tree') ===
              ControlModel.revisionToken('/two', 'delivery/release', 'working-tree')) process.exit(6);
          if (ControlModel.authenticationIssue({{authentication_required: false}}, null)) process.exit(7);
          const exact = {{...option, command_schema: 'agora/application/approve-gate-command/v3',
            reason: 'reviewed', evidence_references: ['repo://report'], precondition_digest: 'b'.repeat(64)}};
          if (ControlModel.preparationIssue(exact, option)) process.exit(8);
          if (!ControlModel.preparationIssue({{...exact, precondition_digest: 'bad'}}, option)) process.exit(9);
          const confirmed = ControlModel.preparedCommand(exact, auth);
          if (confirmed.reason !== 'reviewed' || confirmed.precondition_digest !== 'b'.repeat(64)) process.exit(10);
          if (ControlModel.nextTab('summary', 'End') !== 'activity') process.exit(11);
          if (ControlModel.nextTab('activity', 'Home') !== 'summary') process.exit(12);
        """
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_productive_code_has_no_cli_or_protocol_parser_boundary(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in PACKAGE.rglob("*")
            if path.is_file() and path.suffix in {".py", ".js", ".html"}
        )
        for forbidden in (
            "AgoraCliBoundary",
            "subprocess",
            "._cli",
            "_gate_blockers",
            "parse_front_matter",
            'Path(".agora")',
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
