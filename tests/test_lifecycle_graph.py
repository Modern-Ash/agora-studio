from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from agora_studio.core import ACTIVITY_FIELDS, AgoraCliBoundary, ProjectStore
from agora_studio.git_history import GitHistoryReader, GitReadError
from agora_studio.lifecycle import LifecycleError, build_lifecycle, normalize_lifecycle_query
from agora_studio.server import handle_api, static_response
from tests.test_foundation import make_project


def activity(event_type: str, summary: str, timestamp: str) -> dict[str, str | None]:
    record = {field: None for field in ACTIVITY_FIELDS}
    record.update({
        "timestamp": timestamp,
        "type": event_type,
        "summary": summary,
        "actor": "project:agent",
        "swarm_id": "delivery",
        "work_id": "graph",
        "source": "repo://.agora/events.md",
        "path": "/private/project/.agora/activity.md",
    })
    return record


class LifecycleRunner:
    def __init__(self, events: list[dict[str, str | None]] | None = None) -> None:
        self.events = events or []
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        operation = command[3:]
        if operation == ["status"]:
            data: object = {"project": "lifecycle-test"}
        elif operation == ["work", "list"]:
            data = [{
                "id": "graph", "swarm_id": "delivery", "title": "Graph", "state": "review",
                "operational_status": "active", "acceptance_criteria": {"complete": "done"},
                "satisfied_criteria": ["complete"], "required_artifacts": ["spec", "verification-report"],
                "artifact_kinds": ["spec"], "evidence_results": ["success"], "approval_roles": [],
            }]
        elif operation == ["swarm", "list"]:
            data = [{"id": "delivery", "method": "branching"}]
        elif operation[:2] == ["activity", "list"]:
            data = self.events
        else:
            data = []
        return subprocess.CompletedProcess(command, 0, json.dumps(data), "")


def write_record(path: Path, fields: dict[str, object], heading: str = "Record") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {json.dumps(value)}")
    lines.extend(["---", "", f"# {heading}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def make_lifecycle_project(root: Path) -> Path:
    project = make_project(root, "lifecycle-test")
    method = project / ".agora" / "methods" / "branching"
    write_record(method / "METHOD.md", {
        "schema": "agora/method/v1", "id": "branching", "name": "Branching",
        "work-states": ["draft", "build", "review", "done"], "terminal-state": "done",
    })
    transitions = [
        ("01", "draft", "build", None),
        ("02", "build", "review", None),
        ("03", "review", "build", None),
        ("04", "review", "done", "finish"),
    ]
    for name, source, target, gate in transitions:
        fields: dict[str, object] = {"schema": "agora/transition/v1", "from": source, "to": target, "roles": ["developer"]}
        if gate:
            fields["gate"] = gate
        write_record(method / "transitions" / f"{name}.md", fields)
    write_record(method / "gates" / "finish.md", {
        "schema": "agora/gate/v1", "id": "finish", "require-all-criteria": True,
        "require-required-artifacts": True, "require-successful-evidence": True,
        "required-approval-roles": ["owner"],
    })
    spec = project / "docs" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Version one\n", encoding="utf-8")
    work = project / ".agora" / "swarms" / "delivery" / "work" / "graph"
    write_record(work / "artifacts.md", {"schema": "agora/artifacts/v1"})
    with (work / "artifacts.md").open("a", encoding="utf-8") as stream:
        stream.write("\n| Kind | URI | Produced by | Timestamp |\n| --- | --- | --- | --- |\n| spec | repo://docs/spec.md | project:owner | now |\n")
    return project


def initialize_git(project: Path) -> None:
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.name", "Lifecycle Test"], check=True)
    subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(project), "add", "docs/spec.md"], check=True)
    subprocess.run(["git", "-C", str(project), "commit", "-qm", "docs: add spec"], check=True)


class LifecycleProjectionTests(unittest.TestCase):
    def test_branch_cycle_actual_retries_gate_blockers_and_working_revision(self) -> None:
        events = [
            activity("work.transitioned", "from=draft to=build actor=project:agent", "2026-01-01T00:00:00Z"),
            activity("work.transitioned", "from=build to=review actor=project:agent", "2026-01-02T00:00:00Z"),
            activity("work.transitioned", "from=review to=build actor=project:agent", "2026-01-03T00:00:00Z"),
            activity("work.transitioned", "from=build to=review actor=project:agent", "2026-01-04T00:00:00Z"),
            activity("session.failed", "Session failed", "2026-01-04T01:00:00Z"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            project = make_lifecycle_project(Path(directory))
            initialize_git(project)
            (project / "docs" / "spec.md").write_text("# Version two\n", encoding="utf-8")
            store = ProjectStore(AgoraCliBoundary(runner=LifecycleRunner(events)))
            store.select(str(project))

            projection = build_lifecycle(store, {"swarm": "delivery", "work": "graph"})
            working_detail = GitHistoryReader().detail(project, "docs/spec.md", "working-tree")

        self.assertEqual(["draft", "build", "review", "done"], [item["id"] for item in projection["method"]["states"]])
        self.assertEqual(4, len(projection["method"]["transitions"]))
        self.assertEqual(4, len(projection["actual_path"]["traversals"]))
        self.assertEqual("review", projection["actual_path"]["current_state"])
        completion = next(item for item in projection["method"]["transitions"] if item["to"] == "done")
        self.assertIn("verification-report", completion["blockers"][0])
        self.assertTrue(any("approvals missing" in item for item in completion["blockers"]))
        self.assertEqual("session.failed", projection["actual_path"]["annotations"][0]["type"])
        self.assertEqual("working-tree", projection["specification"]["revisions"][0]["id"])
        self.assertFalse(projection["specification"]["revisions"][0]["approved"])
        self.assertIn("Version two", working_detail["text"])

    def test_git_history_follows_rename_and_revision_detail_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_lifecycle_project(Path(directory))
            initialize_git(project)
            subprocess.run(["git", "-C", str(project), "mv", "docs/spec.md", "docs/renamed.md"], check=True)
            subprocess.run(["git", "-C", str(project), "commit", "-qm", "docs: rename spec"], check=True)
            reader = GitHistoryReader(max_output_bytes=1024)

            _, relative = reader.resolve_repo_file(project, "repo://docs/renamed.md")
            history = reader.history(project, relative)
            detail = reader.detail(project, relative, history["revisions"][0]["id"])

        self.assertEqual(2, len(history["revisions"]))
        self.assertTrue(all(item["kind"] == "commit" for item in history["revisions"]))
        self.assertLessEqual(len(detail["text"].encode()), 1024)

    def test_untracked_working_revision_returns_plain_text_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_lifecycle_project(Path(directory))
            subprocess.run(["git", "init", "-q", str(project)], check=True)

            detail = GitHistoryReader().detail(project, "docs/spec.md", "working-tree")

        self.assertIn("Version one", detail["text"])
        self.assertIn("# Version one", detail["changed_headings"])

    def test_invalid_query_and_symlink_are_rejected_before_unsafe_reads(self) -> None:
        invalid = [
            {"swarm": "../escape", "work": "graph"},
            {"swarm": "delivery", "work": ["one", "two"]},
            {"swarm": "delivery", "work": "graph", "extra": "value"},
        ]
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(LifecycleError):
                normalize_lifecycle_query(query)
        with tempfile.TemporaryDirectory() as directory:
            project = make_lifecycle_project(Path(directory))
            outside = Path(directory) / "outside.md"
            outside.write_text("secret", encoding="utf-8")
            link = project / "docs" / "link.md"
            link.symlink_to(outside)
            with self.assertRaisesRegex(GitReadError, "symbolic link"):
                GitHistoryReader.resolve_repo_file(project, "repo://docs/link.md")

    def test_git_runner_uses_exact_argv_timeout_minimal_environment_and_no_shell(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []
        sha = "a" * 40

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            output = f"{sha}\x1f2026-01-01T00:00:00Z\x1fAgent\x1fSubject\n" if "log" in command else ""
            return subprocess.CompletedProcess(command, 0, output, "")

        reader = GitHistoryReader(runner=runner, timeout_seconds=2.5)
        reader.history(Path("/tmp/a project"), "docs/spec.md")

        self.assertEqual(["git", "-C", "/tmp/a project", "log"], calls[0][0][:4])
        self.assertEqual(["--", "docs/spec.md"], calls[0][0][-2:])
        self.assertEqual(["git", "-C", "/tmp/a project", "status", "--porcelain=v1", "--", "docs/spec.md"], calls[1][0])
        for _, kwargs in calls:
            self.assertFalse(kwargs["shell"])
            self.assertEqual(2.5, kwargs["timeout"])
            self.assertNotIn("HOME", kwargs["env"])
            self.assertEqual("0", kwargs["env"]["GIT_TERMINAL_PROMPT"])

    def test_api_requires_selection_and_returns_safe_partial_without_git(self) -> None:
        status, payload = handle_api(ProjectStore(), "GET", "/api/lifecycle", query={"swarm": "delivery", "work": "graph"})
        self.assertEqual(409, status)
        self.assertEqual("project_required", payload["error"])

        with tempfile.TemporaryDirectory() as directory:
            project = make_lifecycle_project(Path(directory))
            store = ProjectStore(AgoraCliBoundary(runner=LifecycleRunner()))
            store.select(str(project))
            before = {str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest() for path in project.rglob("*") if path.is_file()}
            status, payload = handle_api(store, "GET", "/api/lifecycle", query={"swarm": "delivery", "work": "graph"})
            after = {str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest() for path in project.rglob("*") if path.is_file()}

        self.assertEqual(200, status)
        self.assertTrue(payload["availability"]["partial"])
        self.assertEqual(before, after)


class LifecycleUiTests(unittest.TestCase):
    static = Path(__file__).parents[1] / "agora_studio" / "static"

    def test_model_layout_is_method_agnostic_and_preserves_cycles(self) -> None:
        model = self.static / "lifecycle-model.js"
        script = f"""
require({json.dumps(str(model))});
const method = {{initial_state:'alpha', states:[{{id:'alpha'}},{{id:'beta'}},{{id:'fork'}}], transitions:[
  {{id:'a',from:'alpha',to:'beta'}},{{id:'b',from:'beta',to:'alpha'}},{{id:'c',from:'alpha',to:'fork'}}]}};
const layout = LifecycleModel.layout(method, 700);
const counts = LifecycleModel.traversalCounts([{{from:'alpha',to:'beta'}},{{from:'alpha',to:'beta'}}]);
process.stdout.write(JSON.stringify({{back:layout.edges.find((edge)=>edge.id==='b').backEdge, fork:layout.positions.fork.rank, count:counts.get('alpha\\u0000beta')}}));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        self.assertTrue(output["back"])
        self.assertEqual(1, output["fork"])
        self.assertEqual(2, output["count"])

    def test_assets_interactions_accessibility_and_responsive_contracts(self) -> None:
        html = (self.static / "index.html").read_text(encoding="utf-8")
        javascript = (self.static / "app.js").read_text(encoding="utf-8")
        css = (self.static / "styles.css").read_text(encoding="utf-8")
        body, content_type, cache = static_response("/assets/lifecycle-model.js")

        self.assertEqual("text/javascript; charset=utf-8", content_type)
        self.assertTrue(cache)
        self.assertTrue(body)
        self.assertIn('data-view="lifecycle"', html)
        for contract in ("Fit graph", "Reset view", "Text equivalent", "keyboardSelect", "lifecycleLayers", "revisionDetails", "requestSerial"):
            self.assertIn(contract, javascript)
        self.assertIn("role: \"group\"", javascript)
        self.assertIn("tabindex: \"0\"", javascript)
        self.assertNotIn("innerHTML", javascript)
        self.assertIn("min-width: 320px", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("min-height: 44px", css)


if __name__ == "__main__":
    unittest.main()
