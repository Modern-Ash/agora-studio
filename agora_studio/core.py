"""Project selection and the strictly read-only Agora CLI boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from threading import Lock
from typing import Callable, Mapping, Sequence
import unicodedata


@dataclass(frozen=True)
class CliResult:
    operation: str
    exit_code: int
    data: object
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


class ActivityQueryError(Exception):
    """A rejected Activity query that is safe to return to the browser."""


@dataclass(frozen=True)
class ActivityQuery:
    filters: dict[str, str | None]
    limit: int


ACTIVITY_FIELDS = (
    "timestamp",
    "type",
    "summary",
    "actor",
    "swarm_id",
    "work_id",
    "session_id",
    "tool_run_id",
    "source",
    "path",
)

_ACTIVITY_FLAGS = {
    "type": "--type",
    "actor": "--actor",
    "swarm": "--swarm",
    "work": "--work",
    "session": "--session",
    "tool_run": "--tool-run",
}


def normalize_activity_query(query: Mapping[str, object] | None) -> ActivityQuery:
    """Validate scalar Activity query values before any process is created."""
    values = query or {}
    unknown = set(values) - {*_ACTIVITY_FLAGS, "limit"}
    if unknown:
        raise ActivityQueryError(f"unknown Activity query field: {sorted(unknown)[0]}")

    normalized: dict[str, str | None] = {key: None for key in _ACTIVITY_FLAGS}
    for key, raw in values.items():
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                raise ActivityQueryError(f"Activity query field {key} must be provided once")
            raw = raw[0]
        if not isinstance(raw, str):
            raise ActivityQueryError(f"Activity query field {key} must be a string")
        if len(raw) > 200:
            raise ActivityQueryError(f"Activity query field {key} is longer than 200 characters")
        if any(unicodedata.category(character) == "Cc" for character in raw):
            raise ActivityQueryError(f"Activity query field {key} contains control characters")
        if key in _ACTIVITY_FLAGS:
            normalized[key] = None if raw in ("", "All") else raw

    raw_limit = values.get("limit", "500")
    if isinstance(raw_limit, (list, tuple)):
        if len(raw_limit) != 1:
            raise ActivityQueryError("Activity query field limit must be provided once")
        raw_limit = raw_limit[0]
    try:
        limit = int(raw_limit)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ActivityQueryError("Activity limit must be an integer from 1 through 500") from error
    if not 1 <= limit <= 500:
        raise ActivityQueryError("Activity limit must be an integer from 1 through 500")
    return ActivityQuery(normalized, limit)


Runner = Callable[..., subprocess.CompletedProcess[str]]


class AgoraCliBoundary:
    """Execute only explicitly declared, non-mutating Agora reads."""

    _OPERATIONS: Mapping[str, Sequence[str]] = {
        "status": ("status",),
        "actors": ("actor", "list"),
        "swarms": ("swarm", "list"),
        "work": ("work", "list"),
        "sessions": ("session", "list"),
    }
    _RESULT_TYPES: Mapping[str, type[object]] = {
        "status": dict,
        "actors": list,
        "swarms": list,
        "work": list,
        "sessions": list,
    }

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
                shell=False,
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
        if not isinstance(data, self._RESULT_TYPES[operation]):
            raise SelectionError(operation, project_path, "the Agora CLI returned an invalid result")
        return CliResult(operation, completed.returncode, data, diagnostic)

    def activity(self, project_path: Path, query: ActivityQuery) -> CliResult:
        """Run only the reviewed ``activity list`` operation with validated argv."""
        command = [self._executable, "--project", str(project_path), "activity", "list"]
        for key, flag in _ACTIVITY_FLAGS.items():
            value = query.filters[key]
            if value is not None:
                command.extend((flag, value))
        command.extend(("--limit", str(query.limit)))
        try:
            completed = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
                shell=False,
            )
        except FileNotFoundError as error:
            raise SelectionError("activity", project_path, "the Agora CLI is not available") from error
        except subprocess.TimeoutExpired as error:
            raise SelectionError("activity", project_path, "the Agora Activity read timed out") from error
        except OSError as error:
            raise SelectionError("activity", project_path, "the Agora Activity read could not start") from error

        if completed.returncode != 0:
            raise SelectionError(
                "activity",
                project_path,
                f"Agora could not read durable activity (exit code {completed.returncode})",
            )
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise SelectionError("activity", project_path, "Agora returned invalid Activity JSON") from error
        if not isinstance(data, list):
            raise SelectionError("activity", project_path, "Agora returned an invalid Activity result")
        for item in data:
            if not isinstance(item, dict) or any(
                field not in item or not isinstance(item[field], (str, type(None)))
                for field in ACTIVITY_FIELDS
            ):
                raise SelectionError("activity", project_path, "Agora returned an invalid Activity result")
        events = [{field: item[field] for field in ACTIVITY_FIELDS} for item in data]
        return CliResult("activity", completed.returncode, events, "")

    def project_identity(self, project_path: Path) -> str:
        result = self.execute("status", project_path)
        project = result.data.get("project") if isinstance(result.data, dict) else None
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

    def overview(self) -> dict[str, object]:
        """Read one coherent project snapshot without mutating the selection."""
        with self._lock:
            selection = self._selection
        if selection is None:
            raise SelectionError("overview", "", "a project must be selected first")

        snapshot: dict[str, object] = {"selection": selection.as_dict()}
        for operation in self._cli.allowed_operations:
            snapshot[operation] = self._cli.execute(operation, selection.path).data
        return snapshot

    def activity(self, query: Mapping[str, object] | None = None) -> dict[str, object]:
        """Read a bounded Activity slice while retaining the validated selection."""
        with self._lock:
            selection = self._selection
        if selection is None:
            raise SelectionError("activity", "", "a project must be selected first")
        normalized = normalize_activity_query(query)
        result = self._cli.activity(selection.path, normalized)
        events = result.data if isinstance(result.data, list) else []
        return {
            "selection": selection.as_dict(),
            "filters": normalized.filters,
            "events": events,
            "meta": {
                "count": len(events),
                "limit": normalized.limit,
                "limit_reached": len(events) >= normalized.limit,
            },
        }
