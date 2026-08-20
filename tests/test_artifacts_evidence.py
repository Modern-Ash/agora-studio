from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from agora_studio.artifacts import ArtifactsError, build_artifacts, normalize_artifacts_query
from agora_studio.core import ACTIVITY_FIELDS, AgoraCliBoundary, ProjectStore
from agora_studio.server import handle_api, static_response
from tests.test_foundation import make_project


def activity(
    event_type: str, summary: str, timestamp: str, **overrides: object
) -> dict[str, object]:
    record: dict[str, object] = {field: None for field in ACTIVITY_FIELDS}
    record.update(
        {
            "timestamp": timestamp,
            "type": event_type,
            "summary": summary,
            "actor": "project:agent",
            "swarm_id": "delivery",
            "work_id": "widget",
            "source": "repo://.agora/events.md",
            "path": "/private/project/.agora/activity.md",
        }
    )
    record.update(overrides)
    return record


class ArtifactsRunner:
    def __init__(
        self, events: list[dict[str, object]] | None = None, approval_roles: list[str] | None = None
    ) -> None:
        self.events = events or []
        self.approval_roles = approval_roles if approval_roles is not None else ["spec-owner"]
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        operation = command[3:]
        if operation == ["status"]:
            data: object = {"project": "artifacts-test"}
        elif operation == ["work", "list"]:
            data = [
                {
                    "id": "widget",
                    "swarm_id": "delivery",
                    "title": "Widget",
                    "approval_roles": self.approval_roles,
                }
            ]
        elif operation[:2] == ["activity", "list"]:
            data = self.events
        else:
            data = []
        return subprocess.CompletedProcess(command, 0, json.dumps(data), "")


def write_table(
    path: Path,
    front_matter: dict[str, object],
    heading: str,
    columns: list[str],
    rows: list[list[str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in front_matter.items():
        lines.append(f"{key}: {json.dumps(value)}")
    lines += [
        "---",
        "",
        f"# {heading}",
        "",
        f"| {' | '.join(columns)} |",
        f"| {' | '.join(['---'] * len(columns))} |",
    ]
    for row in rows:
        lines.append(f"| {' | '.join(row)} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_artifacts_project(root: Path, *, with_records: bool = True) -> Path:
    project = make_project(root, "artifacts-test")
    work = project / ".agora" / "swarms" / "delivery" / "work" / "widget"
    rows_artifacts = (
        [
            ["spec", "repo://docs/spec.md", "project:owner", "2026-01-01T00:00:00Z"],
            [
                "verification-report",
                "repo://docs/report.md",
                "project:agent",
                "2026-01-02T00:00:00Z",
            ],
        ]
        if with_records
        else []
    )
    rows_evidence = (
        [
            [
                "automated-verification",
                "success",
                "repo://docs/report.md",
                "project:agent",
                "2026-01-02T00:05:00Z",
            ],
        ]
        if with_records
        else []
    )
    rows_approvals = (
        [
            ["spec-owner", "project:owner", "Accepted", "2026-01-02T01:00:00Z"],
        ]
        if with_records
        else []
    )
    write_table(
        work / "artifacts.md",
        {"schema": "agora/artifacts/v1"},
        "Artifacts",
        ["Kind", "URI", "Produced by", "Timestamp"],
        rows_artifacts,
    )
    write_table(
        work / "evidence.md",
        {"schema": "agora/evidence/v1"},
        "Evidence",
        ["Type", "Result", "Artifact references", "Produced by", "Timestamp"],
        rows_evidence,
    )
    write_table(
        work / "approvals.md",
        {"schema": "agora/approvals/v1"},
        "Approvals",
        ["Role", "Approved by", "Note", "Timestamp"],
        rows_approvals,
    )
    return project


class ArtifactsQueryTests(unittest.TestCase):
    def test_invalid_queries_are_rejected(self) -> None:
        invalid = [
            {"swarm": "../escape", "work": "widget"},
            {"swarm": "delivery", "work": ["a", "b"]},
            {"swarm": "delivery", "work": "widget", "extra": "x"},
            {"swarm": "delivery"},
        ]
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(ArtifactsError):
                normalize_artifacts_query(query)

    def test_valid_query_normalizes(self) -> None:
        self.assertEqual(
            {"swarm": "delivery", "work": "widget"},
            normalize_artifacts_query({"swarm": "delivery", "work": "widget"}),
        )


class ArtifactsProjectionTests(unittest.TestCase):
    def test_listing_reflects_durable_records_with_kind_result_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual(2, len(payload["artifacts"]))
        self.assertEqual("spec", payload["artifacts"][0]["kind"])
        self.assertEqual("repo://docs/spec.md", payload["artifacts"][0]["uri"])
        self.assertEqual(1, len(payload["evidence"]))
        self.assertEqual("success", payload["evidence"][0]["result"])
        self.assertEqual(["repo://docs/report.md"], payload["evidence"][0]["artifact_references"])

    def test_approvals_report_required_roles_and_satisfaction_including_none_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(
                AgoraCliBoundary(runner=ArtifactsRunner(approval_roles=["spec-owner"]))
            )
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual(["spec-owner"], payload["approvals"]["required_roles"])
        self.assertEqual(
            [{"role": "spec-owner", "satisfied": True}], payload["approvals"]["satisfaction"]
        )

        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory), with_records=False)
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner(approval_roles=[])))
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual([], payload["approvals"]["required_roles"])
        self.assertEqual([], payload["approvals"]["satisfaction"])
        self.assertEqual([], payload["artifacts"])
        self.assertEqual([], payload["evidence"])

    def test_missing_approval_role_reports_unsatisfied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory), with_records=False)
            store = ProjectStore(
                AgoraCliBoundary(runner=ArtifactsRunner(approval_roles=["reviewer"]))
            )
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual(
            [{"role": "reviewer", "satisfied": False}], payload["approvals"]["satisfaction"]
        )

    def test_traceability_present_only_with_exact_matching_durable_event(self) -> None:
        events = [
            activity(
                "artifact.added",
                "kind=spec uri=repo://docs/spec.md actor=project:owner",
                "2026-01-01T00:00:01Z",
                session_id="run-session-1",
            ),
            activity(
                "evidence.added",
                "type=automated-verification result=success actor=project:agent",
                "2026-01-02T00:06:00Z",
                tool_run_id="tool-run-9",
            ),
            activity(
                "approval.added",
                "role=spec-owner actor=project:owner delegation=none",
                "2026-01-02T01:00:01Z",
                session_id="run-session-2",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner(events)))
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual("run-session-1", payload["artifacts"][0]["traceability"]["session_id"])
        self.assertIsNone(payload["artifacts"][1]["traceability"])
        self.assertEqual("tool-run-9", payload["evidence"][0]["traceability"]["tool_run_id"])
        self.assertEqual(
            "run-session-2", payload["approvals"]["records"][0]["traceability"]["session_id"]
        )

    def test_traceability_is_absent_without_exact_durable_identifier(self) -> None:
        events = [
            activity(
                "artifact.added",
                "kind=spec uri=repo://docs/spec.md actor=project:owner",
                "2026-01-01T00:00:01Z",
            ),
            activity(
                "work.transitioned",
                "from=draft to=review actor=project:agent",
                "2026-01-01T00:00:02Z",
                session_id="run-unrelated",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner(events)))
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        for artifact in payload["artifacts"]:
            self.assertIsNone(artifact["traceability"])
        for evidence in payload["evidence"]:
            self.assertIsNone(evidence["traceability"])
        for approval in payload["approvals"]["records"]:
            self.assertIsNone(approval["traceability"])

    def test_not_found_work_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            with self.assertRaises(ArtifactsError) as context:
                build_artifacts(store, {"swarm": "delivery", "work": "unknown"})
        self.assertEqual("not_found", context.exception.kind)

    def test_safety_boundary_uses_argv_only_no_shell_and_read_only_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            runner = ArtifactsRunner()
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            store.select(str(project))
            before = {
                str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in project.rglob("*")
                if path.is_file()
            }
            build_artifacts(store, {"swarm": "delivery", "work": "widget"})
            after = {
                str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in project.rglob("*")
                if path.is_file()
            }

        self.assertEqual(before, after)
        for call in runner.calls:
            self.assertEqual(["agora", "--project", str(project)], call[:3])
            self.assertNotIn("shell", call)
        serialized = json.dumps({"path": str(project)})
        self.assertNotIn("credential", serialized.lower())
        self.assertNotIn("private_key", serialized.lower())

    def test_path_traversal_and_symlink_escape_are_rejected(self) -> None:
        with self.assertRaises(ArtifactsError):
            normalize_artifacts_query({"swarm": "../escape", "work": "widget"})

        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            outside = Path(directory) / "outside.md"
            outside.write_text("secret", encoding="utf-8")
            work = project / ".agora" / "swarms" / "delivery" / "work" / "widget"
            (work / "artifacts.md").unlink()
            (work / "artifacts.md").symlink_to(outside)
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual([], payload["artifacts"])
        self.assertTrue(payload["availability"]["partial"])
        self.assertTrue(any("Artifacts are unavailable" in item for item in payload["diagnostics"]))

    def test_non_repo_uri_is_displayed_only_and_not_fetched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            work = project / ".agora" / "swarms" / "delivery" / "work" / "widget"
            write_table(
                work / "artifacts.md",
                {"schema": "agora/artifacts/v1"},
                "Artifacts",
                ["Kind", "URI", "Produced by", "Timestamp"],
                [
                    [
                        "spec",
                        "https://example.invalid/spec.md",
                        "project:owner",
                        "2026-01-01T00:00:00Z",
                    ],
                ],
            )
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            payload = build_artifacts(store, {"swarm": "delivery", "work": "widget"})

        self.assertEqual("https://example.invalid/spec.md", payload["artifacts"][0]["uri"])


class ArtifactsApiTests(unittest.TestCase):
    def test_api_requires_project_selection(self) -> None:
        status, payload = handle_api(
            ProjectStore(), "GET", "/api/artifacts", query={"swarm": "delivery", "work": "widget"}
        )
        self.assertEqual(409, status)
        self.assertEqual("project_required", payload["error"])

    def test_api_returns_400_for_invalid_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            status, payload = handle_api(
                store, "GET", "/api/artifacts", query={"swarm": "delivery"}
            )
        self.assertEqual(400, status)
        self.assertEqual("invalid_query", payload["error"])

    def test_api_returns_404_for_unknown_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            status, payload = handle_api(
                store, "GET", "/api/artifacts", query={"swarm": "delivery", "work": "unknown"}
            )
        self.assertEqual(404, status)
        self.assertEqual("not_found", payload["error"])

    def test_api_returns_200_with_full_projection_and_no_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=ArtifactsRunner()))
            store.select(str(project))
            status, payload = handle_api(
                store, "GET", "/api/artifacts", query={"swarm": "delivery", "work": "widget"}
            )
        self.assertEqual(200, status)
        self.assertEqual(2, len(payload["artifacts"]))
        self.assertIn("approvals", payload)

    def test_query_failure_returns_502_when_cli_fails(self) -> None:
        def failing_runner(
            command: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            operation = command[3:]
            if operation == ["status"]:
                return subprocess.CompletedProcess(
                    command, 0, json.dumps({"project": "artifacts-test"}), ""
                )
            return subprocess.CompletedProcess(command, 1, "", "denied")

        with tempfile.TemporaryDirectory() as directory:
            project = make_artifacts_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=failing_runner))
            store.select(str(project))
            status, payload = handle_api(
                store, "GET", "/api/artifacts", query={"swarm": "delivery", "work": "widget"}
            )
        self.assertEqual(502, status)
        self.assertEqual("artifacts_read_failed", payload["error"])


class ArtifactsUiTests(unittest.TestCase):
    static = Path(__file__).parents[1] / "agora_studio" / "static"

    def test_model_selection_helpers(self) -> None:
        model = self.static / "artifacts-model.js"
        script = f"""
require({json.dumps(str(model))});
const projection = {{
  artifacts: [{{id: 'artifact-0', kind: 'spec'}}],
  evidence: [{{id: 'evidence-0', type: 'automated-verification', traceability: {{session_id: 's1'}}}}],
  approvals: {{records: [{{id: 'approval-0', role: 'spec-owner'}}]}},
}};
const key = ArtifactsModel.itemKey('evidence', projection.evidence[0]);
const found = ArtifactsModel.findSelected(projection, key);
process.stdout.write(JSON.stringify({{
  exists: ArtifactsModel.selectionExists(projection, key),
  missing: ArtifactsModel.selectionExists(projection, 'artifact:none'),
  kind: found.kind,
  traced: ArtifactsModel.hasTraceability(projection.evidence[0]),
  untraced: ArtifactsModel.hasTraceability(projection.artifacts[0]),
}}));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        self.assertTrue(output["exists"])
        self.assertFalse(output["missing"])
        self.assertEqual("evidence", output["kind"])
        self.assertTrue(output["traced"])
        self.assertFalse(output["untraced"])

    def test_assets_accessibility_and_responsive_contracts(self) -> None:
        html = (self.static / "index.html").read_text(encoding="utf-8")
        javascript = (self.static / "app.js").read_text(encoding="utf-8")
        css = (self.static / "styles.css").read_text(encoding="utf-8")
        body, content_type, cache = static_response("/assets/artifacts-model.js")

        self.assertEqual("text/javascript; charset=utf-8", content_type)
        self.assertTrue(cache)
        self.assertTrue(body)
        self.assertIn('data-view="work"', html)
        for contract in (
            '"artifacts"',
            '"evidence"',
            '"approvals"',
            "renderArtifactsTab",
            "renderEvidenceTab",
            "renderApprovalsTab",
            "pendingApprovals",
        ):
            self.assertIn(contract, javascript)
        self.assertIn('role: "tablist"', javascript)
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("min-width: 320px", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("min-height: 44px", css)


if __name__ == "__main__":
    unittest.main()
