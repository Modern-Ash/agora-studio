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
        self.assertEqual(agora_studio.__version__, "0.2.0")
        self.assertEqual(build_parser().parse_args(["--port", "7358"]).port, 7358)
        self.assertIn('dependencies = ["agora-framework>=0.5,<0.6"]', pyproject)
        self.assertIn('version = { attr = "agora_studio.__version__" }', pyproject)

    def test_static_assets_are_packaged_and_exactly_allowlisted(self) -> None:
        package = files("agora_studio") / "static"
        for name in ("index.html", "styles.css", "app.js", "agora-mark.png"):
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

    def test_dashboard_uses_core_terminal_and_blocker_fields(self) -> None:
        model = PACKAGE / "static" / "dashboard-model.js"
        script = f"""
          require({str(model)!r});
          const lifecycle = {{method: {{current_state: 'verifying', states: [
            {{id: 'verifying', terminal: false}}, {{id: 'completed', terminal: true}}
          ], transitions: [{{from: 'verifying', to: 'completed', gate: 'completion',
            blockers: [{{category: 'evidence', message: 'Evidence missing'}},
              {{category: 'approval', message: 'Approval missing', references: ['product-owner']}}],
            required_approval_roles: ['product-owner']}}]}}}};
          if (!DashboardModel.isWorkInProgress({{state: 'verifying'}}, {{lifecycle}})) process.exit(1);
          if (DashboardModel.isWorkInProgress({{state: 'completed'}}, {{lifecycle}})) process.exit(2);
          if (!DashboardModel.evidenceMissing({{state: 'verifying'}}, {{lifecycle}})) process.exit(3);
          if (DashboardModel.pendingGates(lifecycle)[0].id !== 'completion') process.exit(4);
          const detail = {{lifecycle, artifacts: {{approvals: {{records: [{{role: 'product-owner'}}]}},
            evidence: [{{result: 'failure', artifact_references: ['repo://report']}}]}}}};
          if (DashboardModel.pendingApprovals(detail.artifacts, lifecycle).length !== 1) process.exit(5);
          const context = DashboardModel.gateDecisionContext({{swarm_id: 'delivery'}},
            [{{id: 'delivery', assignments: {{'product-owner': 'project:owner'}}}}], detail);
          if (!context.ready || context.evidence.length !== 1) process.exit(6);
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
