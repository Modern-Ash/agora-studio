"""Agora Core application-service gateway and in-memory project selection."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from threading import RLock
from typing import Callable, Mapping, Protocol

CORE_DISTRIBUTION = "agora-framework"
MINIMUM_CORE_VERSION = (0, 8, 0)
MAXIMUM_CORE_VERSION = (0, 9, 0)

SCHEMAS = {
    "overview": "agora/application/project-overview/v2",
    "actor": "agora/application/actor-summary/v1",
    "swarm": "agora/application/swarm-summary/v1",
    "work": "agora/application/work-item-summary/v1",
    "work_detail": "agora/application/work-item-detail/v3",
    "session": "agora/application/session-summary/v1",
    "method": "agora/application/method-summary/v2",
    "method_state": "agora/application/method-state-summary/v1",
    "transition": "agora/application/transition-summary/v1",
    "gate": "agora/application/gate-summary/v2",
    "gate_blocker": "agora/application/gate-blocker-summary/v1",
    "activity": "agora/application/activity-entry/v1",
    "lifecycle": "agora/application/lifecycle-projection/v3",
    "artifact": "agora/application/artifact-summary/v3",
    "evidence": "agora/application/evidence-summary/v3",
    "approval": "agora/application/approval-summary/v2",
    "traceability": "agora/application/traceability-summary/v2",
    "specification": "agora/application/specification-summary/v1",
    "specification_revision_summary": "agora/application/specification-revision-summary/v1",
    "specification_revision": "agora/application/specification-revision-detail/v1",
    "gate_option": "agora/application/gate-decision-option-summary/v3",
    "gate_options": "agora/application/gate-decision-options-projection/v3",
    "work_control": "agora/application/work-control-projection/v3",
}


class CoreGatewayError(Exception):
    """A stable Core read or compatibility failure safe for the HTTP adapter."""

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


class SelectionError(Exception):
    """A safe, actionable project-selection failure."""

    def __init__(self, operation: str, path: object, reason: str, code: str = "selection.invalid"):
        self.operation = operation
        self.path = str(path)
        self.reason = reason
        self.code = code
        super().__init__(f"{operation} failed for {self.path}: {reason}")

    def as_dict(self) -> dict[str, str]:
        return {
            "schema": "agora-studio/api/error/v1",
            "error": "project_selection_failed",
            "code": self.code,
            "operation": self.operation,
            "path": self.path,
            "reason": self.reason,
        }


class ActivityQueryError(Exception):
    """A rejected Activity query that is safe to return to the browser."""


@dataclass(frozen=True)
class ActivityQuery:
    filters: Mapping[str, str | None]
    limit: int


@dataclass(frozen=True)
class ProjectSelection:
    path: Path
    project: str
    core_version: str

    def as_dict(self) -> dict[str, str]:
        return {
            "schema": "agora-studio/api/project-selection/v1",
            "path": str(self.path),
            "project": self.project,
            "core_version": self.core_version,
        }


_ACTIVITY_FIELDS = {
    "type": "type",
    "actor": "actor_id",
    "swarm": "swarm_id",
    "work": "work_id",
    "session": "session_id",
    "tool_run": "tool_run_id",
}


def normalize_activity_query(query: Mapping[str, object] | None) -> ActivityQuery:
    values = query or {}
    unknown = set(values) - {*_ACTIVITY_FIELDS, "limit"}
    if unknown:
        raise ActivityQueryError(f"unknown Activity query field: {sorted(unknown)[0]}")
    normalized: dict[str, str | None] = {key: None for key in _ACTIVITY_FIELDS}
    for key in _ACTIVITY_FIELDS:
        raw = values.get(key)
        if isinstance(raw, (list, tuple)):
            if len(raw) != 1:
                raise ActivityQueryError(f"Activity query field {key} must be provided once")
            raw = raw[0]
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise ActivityQueryError(f"Activity query field {key} must be a string")
        if len(raw) > 200 or any(unicodedata.category(character) == "Cc" for character in raw):
            raise ActivityQueryError(f"Activity query field {key} is invalid")
        normalized[key] = None if raw in ("", "All") else raw
    raw_limit: object = values.get("limit", "500")
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


class ReadGateway(Protocol):
    @property
    def core_version(self) -> str: ...

    def project_overview(self, project: Path) -> dict[str, object]: ...
    def list_actors(self, project: Path) -> list[dict[str, object]]: ...
    def list_swarms(self, project: Path) -> list[dict[str, object]]: ...
    def list_work_items(self, project: Path) -> list[dict[str, object]]: ...
    def get_work_item(self, project: Path, swarm: str, work: str) -> dict[str, object]: ...
    def list_sessions(self, project: Path) -> list[dict[str, object]]: ...
    def activity(self, project: Path, query: ActivityQuery) -> list[dict[str, object]]: ...
    def get_method(self, project: Path, swarm: str) -> dict[str, object]: ...
    def lifecycle(self, project: Path, swarm: str, work: str) -> dict[str, object]: ...
    def artifacts(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]: ...
    def evidence(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]: ...
    def approvals(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]: ...
    def traceability(self, project: Path, swarm: str, work: str) -> dict[str, object]: ...
    def specification(self, project: Path, swarm: str, work: str) -> dict[str, object]: ...
    def specification_revision(
        self, project: Path, swarm: str, work: str, revision: str
    ) -> dict[str, object]: ...
    def work_control(self, project: Path, swarm: str, work: str) -> dict[str, object]: ...


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise CoreGatewayError(
            "core.version-incompatible", f"Agora Core version {value!r} is not supported"
        )
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


class CoreReadGateway:
    """Consume only the public, versioned Agora Core read service."""

    def __init__(
        self,
        service_factory: Callable[[Path], object] | None = None,
        *,
        core_version: str | None = None,
    ) -> None:
        self._service_factory = service_factory
        self._core_version = core_version
        self._bindings: object | None = None

    @property
    def core_version(self) -> str:
        self._ensure_compatible()
        assert self._core_version is not None
        return self._core_version

    def _ensure_compatible(self) -> None:
        if self._core_version is None:
            try:
                self._core_version = version(CORE_DISTRIBUTION)
            except PackageNotFoundError as error:
                raise CoreGatewayError(
                    "core.unavailable",
                    "Agora Core is not installed; Studio requires agora-framework>=0.8,<0.9",
                ) from error
        parsed = _version_tuple(self._core_version)
        if not MINIMUM_CORE_VERSION <= parsed < MAXIMUM_CORE_VERSION:
            raise CoreGatewayError(
                "core.version-incompatible",
                f"Agora Studio requires Agora Core >=0.8,<0.9; found {self._core_version}",
            )

    def _module(self) -> object:
        self._ensure_compatible()
        if self._bindings is None:
            try:
                self._bindings = import_module("agora.application")
            except (ImportError, AttributeError) as error:
                raise CoreGatewayError(
                    "core.version-incompatible",
                    "Agora Core does not expose the required application-service boundary",
                ) from error
        return self._bindings

    def _service(self, project: Path) -> object:
        if self._service_factory is not None:
            self._ensure_compatible()
            return self._service_factory(project)
        module = self._module()
        try:
            return module.AgoraReadService.from_path(project)  # type: ignore[attr-defined]
        except AttributeError as error:
            raise CoreGatewayError(
                "core.version-incompatible", "AgoraReadService is unavailable"
            ) from error

    @staticmethod
    def _payload(value: object, expected_schema: str) -> dict[str, object]:
        try:
            payload = value.to_dict()  # type: ignore[attr-defined]
        except (AttributeError, TypeError) as error:
            raise CoreGatewayError(
                "core.schema-incompatible", f"Core did not return {expected_schema}"
            ) from error
        if not isinstance(payload, dict) or payload.get("schema") != expected_schema:
            found = payload.get("schema") if isinstance(payload, dict) else None
            raise CoreGatewayError(
                "core.schema-incompatible",
                f"Studio requires schema {expected_schema}; found {found!r}",
            )
        return payload

    def _one(self, project: Path, method: str, schema: str, *args: object) -> dict[str, object]:
        retries = 2
        delay = 0.05
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            service = self._service(project)
            try:
                return self._payload(getattr(service, method)(*args), schema)
            except CoreGatewayError:
                raise
            except Exception as error:
                module = self._module()
                application_error = getattr(module, "AgoraApplicationError", ())
                if application_error and isinstance(error, application_error):
                    safe = error.to_dict()
                    code = str(safe.get("code", ""))
                    retryable = bool(safe.get("retryable"))
                    if code == "durable-state.concurrent-edit" and retryable and attempt < retries:
                        last_error = error
                        time.sleep(delay)
                        continue
                    raise CoreGatewayError(code, str(safe["message"])) from error
                raise CoreGatewayError(
                    "core.read-failed", "Agora Core could not read the project"
                ) from error
        assert last_error is not None
        module = self._module()
        application_error = getattr(module, "AgoraApplicationError", ())
        if isinstance(last_error, application_error):  # type: ignore[arg-type]
            safe = last_error.to_dict()  # type: ignore[attr-defined]
            raise CoreGatewayError(str(safe["code"]), str(safe["message"])) from last_error
        raise CoreGatewayError(
            "core.read-failed", "Agora Core could not read the project"
        ) from last_error

    def _many(
        self, project: Path, method: str, schema: str, *args: object
    ) -> list[dict[str, object]]:
        retries = 2
        delay = 0.05
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            service = self._service(project)
            try:
                return [self._payload(item, schema) for item in getattr(service, method)(*args)]
            except CoreGatewayError:
                raise
            except Exception as error:
                module = self._module()
                application_error = getattr(module, "AgoraApplicationError", ())
                if application_error and isinstance(error, application_error):
                    safe = error.to_dict()
                    code = str(safe.get("code", ""))
                    retryable = bool(safe.get("retryable"))
                    if code == "durable-state.concurrent-edit" and retryable and attempt < retries:
                        last_error = error
                        time.sleep(delay)
                        continue
                    raise CoreGatewayError(code, str(safe["message"])) from error
                raise CoreGatewayError(
                    "core.read-failed", "Agora Core could not read the project"
                ) from error
        assert last_error is not None
        module = self._module()
        application_error = getattr(module, "AgoraApplicationError", ())
        if isinstance(last_error, application_error):  # type: ignore[arg-type]
            safe = last_error.to_dict()  # type: ignore[attr-defined]
            raise CoreGatewayError(str(safe["code"]), str(safe["message"])) from last_error
        raise CoreGatewayError(
            "core.read-failed", "Agora Core could not read the project"
        ) from last_error

    def project_overview(self, project: Path) -> dict[str, object]:
        return self._one(project, "project_overview", SCHEMAS["overview"])

    def list_actors(self, project: Path) -> list[dict[str, object]]:
        return self._many(project, "list_actors", SCHEMAS["actor"])

    def list_swarms(self, project: Path) -> list[dict[str, object]]:
        return self._many(project, "list_swarms", SCHEMAS["swarm"])

    def list_work_items(self, project: Path) -> list[dict[str, object]]:
        return self._many(project, "list_work_items", SCHEMAS["work"])

    def get_work_item(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        return self._one(project, "get_work_item", SCHEMAS["work_detail"], swarm, work)

    def list_sessions(self, project: Path) -> list[dict[str, object]]:
        return self._many(project, "list_sessions", SCHEMAS["session"])

    def activity(self, project: Path, query: ActivityQuery) -> list[dict[str, object]]:
        module = self._module()
        filters = module.ActivityFilters(  # type: ignore[attr-defined]
            **{target: query.filters[source] for source, target in _ACTIVITY_FIELDS.items()},
            limit=query.limit,
        )
        return self._many(project, "activity", SCHEMAS["activity"], filters)

    def get_method(self, project: Path, swarm: str) -> dict[str, object]:
        return self._one(project, "get_method", SCHEMAS["method"], swarm)

    def lifecycle(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        return self._one(project, "lifecycle", SCHEMAS["lifecycle"], swarm, work)

    def artifacts(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]:
        return self._many(project, "artifacts", SCHEMAS["artifact"], swarm, work)

    def evidence(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]:
        return self._many(project, "evidence", SCHEMAS["evidence"], swarm, work)

    def approvals(self, project: Path, swarm: str, work: str) -> list[dict[str, object]]:
        return self._many(project, "approvals", SCHEMAS["approval"], swarm, work)

    def traceability(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        return self._one(project, "work_traceability", SCHEMAS["traceability"], swarm, work)

    def specification(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        return self._one(project, "specification_history", SCHEMAS["specification"], swarm, work)

    def specification_revision(
        self, project: Path, swarm: str, work: str, revision: str
    ) -> dict[str, object]:
        return self._one(
            project,
            "specification_revision",
            SCHEMAS["specification_revision"],
            swarm,
            work,
            revision,
        )

    def work_control(self, project: Path, swarm: str, work: str) -> dict[str, object]:
        payload = self._one(
            project,
            "work_control_projection",
            SCHEMAS["work_control"],
            swarm,
            work,
        )
        required = {
            "work": SCHEMAS["work_detail"],
            "lifecycle": SCHEMAS["lifecycle"],
            "traceability": SCHEMAS["traceability"],
            "specification_history": SCHEMAS["specification"],
            "gate_decision_options": SCHEMAS["gate_options"],
        }
        nested = {field: self._nested(payload, field, schema) for field, schema in required.items()}
        snapshot_token = payload.get("snapshot_token")
        if (
            not isinstance(snapshot_token, str)
            or re.fullmatch(r"[0-9a-f]{64}", snapshot_token) is None
        ):
            raise CoreGatewayError(
                "core.schema-incompatible",
                "Core response field snapshot_token must be a lowercase SHA-256 value",
            )
        for field in ("work", "lifecycle", "traceability", "gate_decision_options"):
            identity = (("swarm_id", swarm), ("id" if field == "work" else "work_id", work))
            for identity_field, expected in identity:
                if nested[field].get(identity_field) != expected:
                    raise CoreGatewayError(
                        "core.schema-incompatible",
                        f"Core changed {identity_field} at {field}",
                    )

        state_values = (
            nested["work"].get("state"),
            nested["lifecycle"].get("current_state"),
            nested["traceability"].get("state"),
            nested["gate_decision_options"].get("current_state"),
        )
        if (
            not all(isinstance(value, str) and value for value in state_values)
            or len(set(state_values)) != 1
        ):
            raise CoreGatewayError(
                "core.schema-incompatible",
                "Core work control projection contains inconsistent lifecycle states",
            )
        operational_values = (
            nested["work"].get("operational_status"),
            nested["lifecycle"].get("operational_status"),
            nested["gate_decision_options"].get("operational_status"),
        )
        if (
            not all(isinstance(value, str) and value for value in operational_values)
            or len(set(operational_values)) != 1
        ):
            raise CoreGatewayError(
                "core.schema-incompatible",
                "Core work control projection contains inconsistent operational status",
            )

        materials: dict[str, list[dict[str, object]]] = {}
        for field, schema in (
            ("artifacts", SCHEMAS["artifact"]),
            ("evidence", SCHEMAS["evidence"]),
            ("approvals", SCHEMAS["approval"]),
        ):
            materials[field] = self._nested_many(payload, field, schema)
            work_materials = self._nested_many(nested["work"], field, schema, prefix="work")
            if materials[field] != work_materials:
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    f"Core work control projection contains inconsistent {field}",
                )

        for field, schema in (
            ("artifacts", SCHEMAS["artifact"]),
            ("evidence", SCHEMAS["evidence"]),
        ):
            traced = self._nested_many(nested["traceability"], field, schema, prefix="traceability")
            if materials[field] != traced:
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    f"Core traceability contains inconsistent {field}",
                )

        self._nested_many(
            nested["traceability"], "activity", SCHEMAS["activity"], prefix="traceability"
        )
        self._nested_many(
            nested["lifecycle"], "states", SCHEMAS["method_state"], prefix="lifecycle"
        )
        transitions = self._nested_many(
            nested["lifecycle"], "transitions", SCHEMAS["transition"], prefix="lifecycle"
        )
        gates = self._nested_many(nested["lifecycle"], "gates", SCHEMAS["gate"], prefix="lifecycle")
        for index, transition in enumerate(transitions):
            self._nested_many(
                transition,
                "blockers",
                SCHEMAS["gate_blocker"],
                prefix=f"lifecycle.transitions[{index}]",
            )
        for index, gate in enumerate(gates):
            self._nested_many(
                gate,
                "blockers",
                SCHEMAS["gate_blocker"],
                prefix=f"lifecycle.gates[{index}]",
            )

        self._nested_many(
            nested["specification_history"],
            "revisions",
            SCHEMAS["specification_revision_summary"],
            prefix="specification_history",
        )
        options = self._nested_many(
            nested["gate_decision_options"],
            "options",
            SCHEMAS["gate_option"],
            prefix="gate_decision_options",
        )
        for index, option in enumerate(options):
            if option.get("swarm_id") != swarm or option.get("work_id") != work:
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    f"Core changed work identity at gate_decision_options.options[{index}]",
                )
            self._nested_many(
                option,
                "blockers",
                SCHEMAS["gate_blocker"],
                prefix=f"gate_decision_options.options[{index}]",
            )
            evidence_by_type = option.get("evidence_references_by_type")
            evidence_references = option.get("evidence_references")
            if not isinstance(evidence_by_type, dict) or any(
                not isinstance(kind, str)
                or not kind
                or not isinstance(references, list)
                or any(not isinstance(reference, str) or not reference for reference in references)
                for kind, references in evidence_by_type.items()
            ):
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    "Core response field "
                    f"gate_decision_options.options[{index}].evidence_references_by_type "
                    "must map evidence types to reference arrays",
                )
            if not isinstance(evidence_references, list) or any(
                not isinstance(reference, str) or not reference for reference in evidence_references
            ):
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    "Core response field "
                    f"gate_decision_options.options[{index}].evidence_references "
                    "must be a reference array",
                )
            typed_union = list(
                dict.fromkeys(
                    reference
                    for references in evidence_by_type.values()
                    for reference in references
                )
            )
            if typed_union != evidence_references:
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    "Core gate option contains inconsistent typed evidence references",
                )
            evidence_content = option.get("evidence_content_sha256")
            if not isinstance(evidence_content, dict) or any(
                not isinstance(k, str)
                or not k
                or (v is not None and re.fullmatch(r"[0-9a-f]{64}", v) is None)
                for k, v in evidence_content.items()
            ):
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    "Core response field "
                    f"gate_decision_options.options[{index}].evidence_content_sha256 "
                    "must map references to SHA-256 or null",
                )
            if set(evidence_content.keys()) != set(evidence_references):
                raise CoreGatewayError(
                    "core.schema-incompatible",
                    "Core gate option contains inconsistent evidence_content_sha256 keys",
                )
        return payload

    @staticmethod
    def _nested(
        payload: Mapping[str, object], field: str, schema: str, *, prefix: str = ""
    ) -> dict[str, object]:
        value = payload.get(field)
        location = f"{prefix}.{field}" if prefix else field
        if not isinstance(value, dict) or value.get("schema") != schema:
            found = value.get("schema") if isinstance(value, dict) else None
            raise CoreGatewayError(
                "core.schema-incompatible",
                f"Studio requires schema {schema} at {location}; found {found!r}",
            )
        return value

    @classmethod
    def _nested_many(
        cls,
        payload: Mapping[str, object],
        field: str,
        schema: str,
        *,
        prefix: str = "",
    ) -> list[dict[str, object]]:
        values = payload.get(field)
        location = f"{prefix}.{field}" if prefix else field
        if not isinstance(values, list):
            raise CoreGatewayError(
                "core.schema-incompatible", f"Core response field {location} must be an array"
            )
        return [cls._nested({"item": value}, "item", schema, prefix=location) for value in values]


class ProjectStore:
    """Atomically retain one validated project and expose Core-backed projections."""

    def __init__(self, gateway: ReadGateway | None = None) -> None:
        self._gateway = gateway or CoreReadGateway()
        self._selection: ProjectSelection | None = None
        self._lock = RLock()

    @property
    def selection(self) -> ProjectSelection | None:
        with self._lock:
            return self._selection

    @property
    def gateway(self) -> ReadGateway:
        return self._gateway

    def _selected(self, operation: str) -> ProjectSelection:
        selection = self.selection
        if selection is None:
            raise SelectionError(operation, "", "a project must be selected first")
        return selection

    def select(self, requested_path: object) -> ProjectSelection:
        operation = "select_project"
        if not isinstance(requested_path, str) or not requested_path.strip():
            raise SelectionError(
                operation, requested_path, "a non-empty directory path is required"
            )
        candidate = Path(requested_path).expanduser()
        try:
            canonical = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise SelectionError(
                operation, requested_path, "the path does not exist or cannot be resolved"
            ) from error
        if not canonical.is_dir():
            raise SelectionError(operation, canonical, "the path is not a directory")
        try:
            overview = self._gateway.project_overview(canonical)
            core_version = self._gateway.core_version
        except CoreGatewayError as error:
            raise SelectionError(operation, canonical, error.reason, error.code) from error
        project = overview.get("project")
        if not isinstance(project, str) or not project:
            raise SelectionError(
                operation,
                canonical,
                "Agora Core returned no durable project identity",
                "core.schema-incompatible",
            )
        validated = ProjectSelection(canonical, project, core_version)
        with self._lock:
            self._selection = validated
        return validated

    def overview(self) -> dict[str, object]:
        selection = self._selected("overview")
        return {
            "schema": "agora-studio/api/overview/v1",
            "selection": selection.as_dict(),
            "status": self._gateway.project_overview(selection.path),
            "actors": self._gateway.list_actors(selection.path),
            "swarms": self._gateway.list_swarms(selection.path),
            "work": self._gateway.list_work_items(selection.path),
            "sessions": self._gateway.list_sessions(selection.path),
        }

    def collection(self, kind: str) -> dict[str, object]:
        selection = self._selected(kind)
        readers = {
            "actors": self._gateway.list_actors,
            "swarms": self._gateway.list_swarms,
            "work-items": self._gateway.list_work_items,
            "sessions": self._gateway.list_sessions,
        }
        if kind not in readers:
            raise CoreGatewayError("core.invalid-query", "unknown Core collection")
        return {
            "schema": f"agora-studio/api/{kind}/v1",
            "selection": selection.as_dict(),
            "items": readers[kind](selection.path),
        }

    def activity(self, query: Mapping[str, object] | None = None) -> dict[str, object]:
        selection = self._selected("activity")
        normalized = normalize_activity_query(query)
        events = self._gateway.activity(selection.path, normalized)
        return {
            "schema": "agora-studio/api/activity/v1",
            "selection": selection.as_dict(),
            "filters": dict(normalized.filters),
            "events": events,
            "meta": {
                "count": len(events),
                "limit": normalized.limit,
                "limit_reached": len(events) >= normalized.limit,
            },
        }
