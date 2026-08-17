"""Project selection and the strictly read-only Agora CLI boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from threading import Lock
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class CliResult:
    operation: str
    exit_code: int
    data: Mapping[str, object] | None
    diagnostic: str


@dataclass(frozen=True)
class ProjectSelection:
    path: Path
    project: str

    def as_dict(self) -> dict[str, str]:
        return {"path": str(self.path), "project": self.project}


class SelectionError(Exception):
    """A safe, actionable project-selection failure."""

    def __init__(self, operation: str, path: object, reason: str):
        self.operation = operation
        self.path = str(path)
        self.reason = reason
        super().__init__(f"{operation} failed for {self.path}: {reason}")

    def as_dict(self) -> dict[str, str]:
        return {
            "error": "project_selection_failed",
            "operation": self.operation,
            "path": self.path,
            "reason": self.reason,
        }


Runner = Callable[..., subprocess.CompletedProcess[str]]


class AgoraCliBoundary:
    """Execute only explicitly declared, non-mutating Agora reads."""

    _OPERATIONS: Mapping[str, Sequence[str]] = {"status": ("status",)}

    def __init__(
        self,
        executable: str = "agora",
        runner: Runner = subprocess.run,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._executable = executable
        self._runner = runner
        self._timeout_seconds = timeout_seconds

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return tuple(self._OPERATIONS)

    def execute(self, operation: str, project_path: Path) -> CliResult:
        arguments = self._OPERATIONS.get(operation)
        if arguments is None:
            raise SelectionError(
                operation,
                project_path,
                "the Agora CLI operation is not in the read-only allowlist",
            )

        command = [self._executable, "--project", str(project_path), *arguments]
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError as error:
            raise SelectionError(operation, project_path, "the Agora CLI is not available") from error
        except subprocess.TimeoutExpired as error:
            raise SelectionError(operation, project_path, "the Agora CLI read timed out") from error
        except OSError as error:
            raise SelectionError(operation, project_path, f"the Agora CLI could not start: {error}") from error

        diagnostic = completed.stderr.strip()
        if completed.returncode != 0:
            reason = diagnostic or f"Agora CLI exited with code {completed.returncode}"
            raise SelectionError(operation, project_path, reason)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise SelectionError(operation, project_path, "the Agora CLI returned invalid JSON") from error
        if not isinstance(data, dict):
            raise SelectionError(operation, project_path, "the Agora CLI returned an invalid result")
        return CliResult(operation, completed.returncode, data, diagnostic)

    def project_identity(self, project_path: Path) -> str:
        result = self.execute("status", project_path)
        project = result.data.get("project") if result.data else None
        if not isinstance(project, str) or not project.strip():
            raise SelectionError("status", project_path, "the Agora CLI did not return a project identity")
        return project


class ProjectStore:
    """Atomically retain one validated project selection in memory."""

    def __init__(self, cli: AgoraCliBoundary | None = None) -> None:
        self._cli = cli or AgoraCliBoundary()
        self._selection: ProjectSelection | None = None
        self._lock = Lock()

    @property
    def selection(self) -> ProjectSelection | None:
        with self._lock:
            return self._selection

    def select(self, requested_path: object) -> ProjectSelection:
        operation = "select_project"
        if not isinstance(requested_path, str) or not requested_path.strip():
            raise SelectionError(operation, requested_path, "a non-empty directory path is required")

        candidate = Path(requested_path).expanduser()
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise SelectionError(operation, requested_path, "the path does not exist or cannot be resolved") from error
        if not canonical.is_dir():
            raise SelectionError(operation, canonical, "the path is not a directory")

        registry = canonical / ".agora" / "project.md"
        try:
            with registry.open("rb") as stream:
                stream.read(1)
        except OSError as error:
            raise SelectionError(
                operation,
                canonical,
                "the directory is not a readable Agora project (.agora/project.md is unavailable)",
            ) from error

        # Validate completely before replacing the previous useful selection.
        project = self._cli.project_identity(canonical)
        validated = ProjectSelection(path=canonical, project=project)
        with self._lock:
            self._selection = validated
        return validated
