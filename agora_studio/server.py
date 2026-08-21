"""Loopback-only HTTP interface for Agora Studio."""

from __future__ import annotations

import hmac
import json
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Mapping
from urllib.parse import parse_qs, urlsplit

from .artifacts import ArtifactsError, build_artifacts
from .commands import (
    CommandAdapterError,
    CoreCommandGateway,
    GateCommandGateway,
    normalize_gate_approval,
)
from .core import ActivityQueryError, CoreGatewayError, ProjectStore, SelectionError
from .lifecycle import LifecycleError, build_lifecycle, normalize_lifecycle_query


class StartupError(Exception):
    """The local server could not bind safely."""


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        store: ProjectStore,
        commands: GateCommandGateway,
        csrf_token: str | None = None,
    ):
        self.store = store
        self.commands = commands
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)
        self.command_lock = Lock()
        super().__init__(server_address, handler)


_STATIC_ROOT = Path(__file__).with_name("static")
_ASSETS = {
    "styles.css": (_STATIC_ROOT / "styles.css", "text/css; charset=utf-8"),
    "activity-model.js": (_STATIC_ROOT / "activity-model.js", "text/javascript; charset=utf-8"),
    "lifecycle-model.js": (_STATIC_ROOT / "lifecycle-model.js", "text/javascript; charset=utf-8"),
    "artifacts-model.js": (_STATIC_ROOT / "artifacts-model.js", "text/javascript; charset=utf-8"),
    "dashboard-model.js": (_STATIC_ROOT / "dashboard-model.js", "text/javascript; charset=utf-8"),
    "control-model.js": (_STATIC_ROOT / "control-model.js", "text/javascript; charset=utf-8"),
    "app.js": (_STATIC_ROOT / "app.js", "text/javascript; charset=utf-8"),
    "agora-mark.png": (_STATIC_ROOT / "agora-mark.png", "image/png"),
    "agora-logo.png": (_STATIC_ROOT / "agora-logo.png", "image/png"),
}
_WORK_ROUTE = re.compile(
    r"/api/v1/work-items/(?P<swarm>[a-z0-9][a-z0-9._-]{0,127})/"
    r"(?P<work>[a-z0-9][a-z0-9._-]{0,127})"
)
_APPROVAL_ROUTE = re.compile(_WORK_ROUTE.pattern + r"/approvals")
_PREPARE_APPROVAL_ROUTE = re.compile(_APPROVAL_ROUTE.pattern + r"/prepare")
_REVISION_ROUTE = re.compile(
    r"/api/v1/specification-revisions/(?P<revision>[A-Za-z0-9][A-Za-z0-9._-]{0,127})"
)
_MAX_JSON_BODY = 65_536
_CSP = (
    "default-src 'self'; base-uri 'none'; connect-src 'self'; "
    "font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
    "img-src 'self'; object-src 'none'; script-src 'self'; style-src 'self'"
)

_COMMAND_STATUS = {
    "command.actor-unauthorized": 403,
    "command.gate-already-resolved": 409,
    "command.stale-precondition": 409,
    "command.governed-material-stale": 409,
    "lifecycle.precondition-failed": 409,
    "command.preparation-expired": 410,
    "command.evidence-missing": 422,
    "gate.evidence-missing": 422,
    "command.signature-invalid": 422,
    "command.signature-required": 428,
    "command.persistence-failed": 503,
    "transaction.commit-failed": 503,
    "transaction.rollback-failed": 503,
    "transaction.indeterminate": 503,
    "durable-state.concurrent-edit": 409,
    "command.version-incompatible": 426,
    "core.schema-incompatible": 426,
    "command.project-identity-mismatch": 409,
    "command.invalid": 400,
    "invalid_request": 400,
}


def _error(code: str, reason: str) -> dict[str, str]:
    return {"schema": "agora-studio/api/error/v1", "error": code, "reason": reason}


def _core_status(error: CoreGatewayError) -> int:
    if error.code in {"core.unavailable", "core.version-incompatible", "core.schema-incompatible"}:
        return 426
    if error.code == "read.resource-not-found":
        return 404
    if error.code == "read.invalid-query":
        return 400
    if error.code == "read.invalid-durable-state":
        return 422
    return 502


def static_response(route: str) -> tuple[bytes, str, bool] | None:
    """Resolve only the exact local interface files exposed by Studio."""
    if route == "/":
        path = _STATIC_ROOT / "index.html"
        content_type = "text/html; charset=utf-8"
        cache = False
    elif route.startswith("/assets/"):
        name = route.removeprefix("/assets/")
        if "/" in name or name not in _ASSETS:
            return None
        path, content_type = _ASSETS[name]
        cache = True
    else:
        return None
    try:
        return path.read_bytes(), content_type, cache
    except OSError:
        return None


def _require_selection(store: ProjectStore, message: str) -> tuple[int, object] | None:
    if store.selection is None:
        return 409, _error("project_required", message)
    return None


def handle_api(
    store: ProjectStore,
    method: str,
    route: str,
    payload: object | None = None,
    query: Mapping[str, object] | None = None,
    commands: GateCommandGateway | None = None,
    csrf_token: str | None = None,
) -> tuple[int, object]:
    """Handle Studio semantics independently from the network security adapter."""
    prepare_match = _PREPARE_APPROVAL_ROUTE.fullmatch(route)
    if method == "POST" and prepare_match is not None:
        required = _require_selection(
            store, "Select a local Agora project before preparing a gate decision."
        )
        if required is not None:
            return required
        selection = store.selection
        assert selection is not None
        try:
            request = normalize_gate_approval(payload)
            prepared = (commands or CoreCommandGateway()).prepare_gate(
                selection,
                prepare_match.group("swarm"),
                prepare_match.group("work"),
                request,
            )
        except CommandAdapterError as error:
            return _COMMAND_STATUS.get(error.code, 500), _error(error.code, error.reason)
        return 200, {
            "schema": "agora-studio/api/prepared-gate-decision/v3",
            "preparation": prepared,
        }

    approval_match = _APPROVAL_ROUTE.fullmatch(route)
    if method == "POST" and approval_match is not None:
        required = _require_selection(
            store, "Select a local Agora project before recording a gate decision."
        )
        if required is not None:
            return required
        selection = store.selection
        assert selection is not None
        try:
            request = normalize_gate_approval(payload, for_confirmation=True)
            projection = (commands or CoreCommandGateway()).approve_gate(
                selection,
                approval_match.group("swarm"),
                approval_match.group("work"),
                request,
            )
        except CommandAdapterError as error:
            return _COMMAND_STATUS.get(error.code, 500), _error(error.code, error.reason)
        return 200, {
            "schema": "agora-studio/api/gate-decision/v3",
            "status": "persisted",
            "projection": projection,
        }

    if method == "GET" and route == "/api/v1/project":
        selection = store.selection
        return 200, {
            "schema": "agora-studio/api/session/v1",
            "project": selection.as_dict() if selection else None,
            "csrf_token": csrf_token,
        }
    if method == "POST" and route == "/api/v1/projects/select":
        if not isinstance(payload, dict):
            return 400, _error("invalid_request", "the JSON body must be an object")
        try:
            selected = store.select(payload.get("path"))
        except SelectionError as error:
            status = 426 if error.code.startswith("core.") else 400
            return status, error.as_dict()
        return 200, {
            "schema": "agora-studio/api/project-opened/v1",
            "status": "opened",
            "project": selected.as_dict(),
        }

    if method != "GET":
        return 404, _error("not_found", "the requested API route does not exist")
    required = _require_selection(
        store, "Select a local Agora project before loading project data."
    )
    if required is not None:
        return required

    try:
        if route == "/api/v1/overview":
            return 200, store.overview()
        collections = {
            "/api/v1/actors": "actors",
            "/api/v1/swarms": "swarms",
            "/api/v1/work-items": "work-items",
            "/api/v1/sessions": "sessions",
        }
        if route in collections:
            return 200, store.collection(collections[route])
        if route == "/api/v1/activity":
            return 200, store.activity(query)
        if route == "/api/v1/lifecycle":
            return 200, build_lifecycle(store, query)
        if route in {
            "/api/v1/artifacts",
            "/api/v1/evidence",
            "/api/v1/approvals",
            "/api/v1/traceability",
        }:
            projection = build_artifacts(store, query)
            if route == "/api/v1/artifacts":
                return 200, projection
            field = route.rsplit("/", 1)[-1]
            return 200, {
                "schema": f"agora-studio/api/{field}/v1",
                "selection": projection["selection"],
                "scope": projection["scope"],
                field: projection[field],
            }
        if route == "/api/v1/specification-history":
            normalized = query or {}
            lifecycle = build_lifecycle(store, normalized)
            return 200, {
                "schema": "agora-studio/api/specification-history/v1",
                "selection": lifecycle["selection"],
                "scope": lifecycle["scope"],
                "specification": lifecycle["specification"],
            }
        revision_match = _REVISION_ROUTE.fullmatch(route)
        if revision_match is not None:
            normalized = normalize_lifecycle_query(query)
            selection = store.selection
            assert selection is not None
            revision = store.gateway.specification_revision(
                selection.path,
                normalized["swarm"],
                normalized["work"],
                revision_match.group("revision"),
            )
            return 200, {
                "schema": "agora-studio/api/specification-revision-detail/v1",
                "selection": selection.as_dict(),
                "scope": {
                    "swarm_id": normalized["swarm"],
                    "work_id": normalized["work"],
                },
                "revision": revision,
            }
        work_match = _WORK_ROUTE.fullmatch(route)
        if work_match is not None:
            selection = store.selection
            assert selection is not None
            control = store.gateway.work_control(
                selection.path, work_match.group("swarm"), work_match.group("work")
            )
            return 200, {
                "schema": "agora-studio/api/work-item-detail/v3",
                "selection": selection.as_dict(),
                "control": control,
            }
    except ActivityQueryError as error:
        return 400, _error("invalid_activity_query", str(error))
    except LifecycleError as error:
        return (404 if error.kind == "not_found" else 400), _error(error.kind, error.reason)
    except ArtifactsError as error:
        return (404 if error.kind == "not_found" else 400), _error(error.kind, error.reason)
    except SelectionError as error:
        return 409, _error("project_required", error.reason)
    except CoreGatewayError as error:
        return _core_status(error), _error(error.code, error.reason)
    return 404, _error("not_found", "the requested API route does not exist")


def _handler() -> type[BaseHTTPRequestHandler]:
    class StudioHandler(BaseHTTPRequestHandler):
        server: StudioServer

        def _send_json(self, status: int, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, body, "application/json; charset=utf-8", cache=False)

        def _send_bytes(self, status: int, body: bytes, content_type: str, *, cache: bool) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=3600" if cache else "no-store")
            self.send_header("Content-Security-Policy", _CSP)
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _host_allowed(self) -> bool:
            host = self.headers.get("Host", "")
            port = self.server.server_address[1]
            return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def _origin_allowed(self) -> bool:
            origin = self.headers.get("Origin", "")
            port = self.server.server_address[1]
            return origin in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

        def _secure_request(self) -> bool:
            if not self._host_allowed():
                self._send_json(
                    421, _error("invalid_host", "Host must identify this loopback server")
                )
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if not self._secure_request():
                return
            parsed = urlsplit(self.path)
            route = parsed.path
            resolved = static_response(route)
            if resolved is not None:
                body, content_type, cache = resolved
                self._send_bytes(200, body, content_type, cache=cache)
                return
            if route.startswith("/assets/"):
                self._send_json(404, _error("not_found", "asset not found"))
                return
            query = parse_qs(parsed.query, keep_blank_values=True)
            status, payload = handle_api(
                self.server.store,
                "GET",
                route,
                query=query,
                csrf_token=self.server.csrf_token,
            )
            self._send_json(status, payload)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if not self._secure_request():
                return
            route = urlsplit(self.path).path
            if (
                route != "/api/v1/projects/select"
                and _APPROVAL_ROUTE.fullmatch(route) is None
                and _PREPARE_APPROVAL_ROUTE.fullmatch(route) is None
            ):
                self._send_json(404, _error("not_found", "the requested API route does not exist"))
                return
            if not self._origin_allowed():
                self._send_json(403, _error("invalid_origin", "Origin must match Studio loopback"))
                return
            supplied = self.headers.get("X-Agora-Studio-CSRF", "")
            if not hmac.compare_digest(supplied, self.server.csrf_token):
                self._send_json(
                    403, _error("csrf_rejected", "a valid Studio CSRF token is required")
                )
                return
            media_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                self._send_json(
                    415, _error("invalid_request", "Content-Type must be application/json")
                )
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, _error("invalid_request", "invalid content length"))
                return
            if length <= 0:
                self._send_json(400, _error("invalid_request", "a JSON request body is required"))
                return
            if length > _MAX_JSON_BODY:
                self._send_json(
                    413, _error("invalid_request", "the JSON request body is too large")
                )
                return
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(
                    400, _error("invalid_request", "the request body is not valid JSON")
                )
                return
            if (
                _APPROVAL_ROUTE.fullmatch(route) is not None
                or _PREPARE_APPROVAL_ROUTE.fullmatch(route) is not None
            ):
                with self.server.command_lock:
                    status, response = handle_api(
                        self.server.store,
                        "POST",
                        route,
                        payload,
                        commands=self.server.commands,
                    )
            else:
                status, response = handle_api(
                    self.server.store,
                    "POST",
                    route,
                    payload,
                    commands=self.server.commands,
                )
            self._send_json(status, response)

        def log_message(self, format: str, *args: object) -> None:
            return

    return StudioHandler


def create_server(
    port: int = 7357,
    store: ProjectStore | None = None,
    commands: GateCommandGateway | None = None,
    csrf_token: str | None = None,
) -> StudioServer:
    if not 0 <= port <= 65535:
        raise StartupError(f"could not bind the local server: invalid port {port}")
    try:
        return StudioServer(
            ("127.0.0.1", port),
            _handler(),
            store or ProjectStore(),
            commands or CoreCommandGateway(),
            csrf_token,
        )
    except OSError as error:
        raise StartupError(
            f"could not bind the local server on 127.0.0.1:{port}: {error}"
        ) from error


def server_url(server: StudioServer) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"
