from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agora_studio.core import AgoraCliBoundary, ProjectStore, SelectionError
from agora_studio.server import StartupError, create_server, handle_api


class RecordingRunner:
    def __init__(
        self, project: str = "test-project", returncode: int = 0, stderr: str = ""
    ) -> None:
        self.project = project
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        stdout = json.dumps({"project": self.project}) if self.returncode == 0 else ""
        return subprocess.CompletedProcess(command, self.returncode, stdout, self.stderr)


def make_project(root: Path, name: str = "test-project") -> Path:
    project = root / name
    registry = project / ".agora" / "project.md"
    registry.parent.mkdir(parents=True)
    registry.write_text(f'---\nproject: "{name}"\n---\n', encoding="utf-8")
    (project / "content.txt").write_text("unchanged\n", encoding="utf-8")
    return project


class CliBoundaryTests(unittest.TestCase):
    def test_allowed_read_uses_separate_arguments_and_structured_result(self) -> None:
        runner = RecordingRunner()
        boundary = AgoraCliBoundary(runner=runner)
        path = Path("/tmp/a project")

        result = boundary.execute("status", path)

        self.assertEqual(["agora", "--project", "/tmp/a project", "status"], runner.calls[0])
        self.assertEqual(0, result.exit_code)
        self.assertEqual("test-project", result.data["project"])
        self.assertEqual("", result.diagnostic)

    def test_unlisted_operation_is_rejected_before_process_creation(self) -> None:
        runner = RecordingRunner()
        boundary = AgoraCliBoundary(runner=runner)

        with self.assertRaisesRegex(SelectionError, "not in the read-only allowlist"):
            boundary.execute("work.transition", Path("/tmp/project"))

        self.assertEqual([], runner.calls)

    def test_cli_failure_and_invalid_output_are_read_errors(self) -> None:
        failed = AgoraCliBoundary(runner=RecordingRunner(returncode=2, stderr="invalid project"))
        with self.assertRaisesRegex(SelectionError, "invalid project"):
            failed.project_identity(Path("/tmp/project"))

        def invalid_runner(
            command: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 0, "not-json", "")

        with self.assertRaisesRegex(SelectionError, "invalid JSON"):
            AgoraCliBoundary(runner=invalid_runner).project_identity(Path("/tmp/project"))


class SelectionTests(unittest.TestCase):
    def test_valid_project_is_canonical_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root)
            store = ProjectStore(AgoraCliBoundary(runner=RecordingRunner()))

            first = store.select(str(project / ".." / project.name))
            second = store.select(str(project))

            self.assertEqual(project.resolve(), first.path)
            self.assertEqual(first, second)
            self.assertEqual("test-project", second.project)

    def test_valid_selection_is_replaced_only_after_new_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = make_project(root, "first")
            second = make_project(root, "second")
            runner = RecordingRunner(project="first")
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            store.select(str(first))
            runner.project = "second"

            selected = store.select(str(second))

            self.assertEqual(second.resolve(), selected.path)
            self.assertEqual("second", selected.project)

    def test_invalid_paths_preserve_previous_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = make_project(root)
            store = ProjectStore(AgoraCliBoundary(runner=RecordingRunner()))
            original = store.select(str(project))

            for invalid in (root / "missing", root / "plain"):
                if invalid.name == "plain":
                    invalid.mkdir()
                with self.assertRaises(SelectionError) as raised:
                    store.select(str(invalid))
                self.assertIn(str(invalid), str(raised.exception))
                self.assertEqual(original, store.selection)

    def test_regular_file_is_rejected_as_a_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "project.md"
            candidate.write_text("not a directory\n", encoding="utf-8")
            store = ProjectStore(AgoraCliBoundary(runner=RecordingRunner()))

            with self.assertRaisesRegex(SelectionError, "not a directory"):
                store.select(str(candidate))

    def test_cli_rejection_preserves_previous_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = make_project(root, "first")
            rejected = make_project(root, "rejected")
            runner = RecordingRunner(project="first")
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            original = store.select(str(first))
            runner.returncode = 2
            runner.stderr = "invalid Agora records"

            with self.assertRaisesRegex(SelectionError, "invalid Agora records"):
                store.select(str(rejected))

            self.assertEqual(original, store.selection)


class ServerTests(unittest.TestCase):
    def test_server_binds_only_to_ipv4_loopback_and_reports_ready(self) -> None:
        store = ProjectStore(AgoraCliBoundary(runner=RecordingRunner()))
        sentinel = object()
        with patch("agora_studio.server.StudioServer", return_value=sentinel) as server_type:
            server = create_server(7357, store)

        self.assertIs(sentinel, server)
        self.assertEqual(("127.0.0.1", 7357), server_type.call_args.args[0])
        self.assertIs(store, server_type.call_args.args[2])
        status, payload = handle_api(store, "GET", "/")
        self.assertEqual(200, status)
        self.assertEqual("ready", payload["status"])
        self.assertIsNone(payload["project"])

    def test_occupied_port_has_clear_startup_failure(self) -> None:
        port = 7357
        with patch(
            "agora_studio.server.StudioServer", side_effect=OSError(98, "Address already in use")
        ):
            with self.assertRaisesRegex(
                StartupError, rf"127\.0\.0\.1:{port}.*Address already in use"
            ):
                create_server(port)

    def test_end_to_end_selection_and_reads_do_not_mutate_project_or_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = make_project(Path(directory))
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            before_files = self._snapshot(project)
            before_git = self._git_status(project)
            runner = RecordingRunner()
            store = ProjectStore(AgoraCliBoundary(runner=runner))
            status, opened = handle_api(
                store, "POST", "/api/projects/select", {"path": str(project)}
            )
            self.assertEqual(200, status)
            self.assertEqual("opened", opened["status"])
            status, current = handle_api(store, "GET", "/api/project")
            self.assertEqual(200, status)
            self.assertEqual("test-project", current["project"]["project"])

            self.assertEqual(before_files, self._snapshot(project))
            self.assertEqual(before_git, self._git_status(project))
            self.assertEqual(
                [["agora", "--project", str(project.resolve()), "status"]], runner.calls
            )

    @staticmethod
    def _snapshot(project: Path) -> dict[str, str]:
        return {
            str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(project.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(project).parts
        }

    @staticmethod
    def _git_status(project: Path) -> str:
        result = subprocess.run(
            ["git", "-C", str(project), "status", "--porcelain=v1"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout


if __name__ == "__main__":
    unittest.main()
