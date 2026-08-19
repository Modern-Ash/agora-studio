"""Loopback-only HTTP interface for Agora Studio."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, urlsplit

from .artifacts import ArtifactsError, build_artifacts
from .core import ActivityQueryError, ProjectStore, SelectionError
from .git_history import GitReadError
from .lifecycle import LifecycleError, build_lifecycle, build_revision_detail


class StartupError(Exception):
    """The local server could not bind safely."""


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], store: ProjectStore):
        self.store = store
        super().__init__(server_address, handler)


_STATIC_ROOT = Path(__file__).with_name("static")
_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = {
    "styles.css": (_STATIC_ROOT / "styles.css", "text/css; charset=utf-8"),
    "activity-model.js": (_STATIC_ROOT / "activity-model.js", "text/javascript; charset=utf-8"),
    "lifecycle-model.js": (_STATIC_ROOT / "lifecycle-model.js", "text/javascript; charset=utf-8"),
    "artifacts-model.js": (_STATIC_ROOT / "artifacts-model.js", "text/javascript; charset=utf-8"),
    "app.js": (_STATIC_ROOT / "app.js", "text/javascript; charset=utf-8"),
    "agora-logo.png": (_REPOSITORY_ROOT / "agora-logo.png", "image/png"),
}


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


def handle_api(
    store: ProjectStore,
    method: str,
    route: str,
    payload: object | None = None,
    query: Mapping[str, object] | None = None,
) -> tuple[int, object]:
    """Handle Studio semantics independently from the network adapter."""
    selection = store.selection
    if method == "GET" and route == "/":
        return 200, {
            "status": "ready",
            "message": "Agora Studio is ready for a project selection",
            "project": selection.as_dict() if selection else None,
        }
    if method == "GET" and route == "/api/project":
        return 200, {"project": selection.as_dict() if selection else None}
    if method == "GET" and route == "/api/overview":
        if selection is None:
            return 409, {
                "error": "project_required",
                "reason": "Select a local Agora project before loading its overview.",
            }
        try:
            return 200, store.overview()
        except SelectionError as error:
            return 502, {
                "error": "project_overview_failed",
                "operation": error.operation,
                "reason": error.reason,
            }
    if method == "GET" and route == "/api/activity":
        if selection is None:
            return 409, {
                "error": "project_required",
                "reason": "Select a local Agora project before loading its activity.",
            }
        try:
            return 200, store.activity(query)
        except ActivityQueryError as error:
            return 400, {"error": "invalid_activity_query", "reason": str(error)}
        except SelectionError as error:
            return 502, {
                "error": "activity_query_failed",
                "operation": error.operation,
                "reason": error.reason,
            }
    if method == "GET" and route in ("/api/lifecycle", "/api/lifecycle/revision"):
        if selection is None:
            return 409, {
                "error": "project_required",
                "reason": "Select a local Agora project before loading lifecycle data.",
            }
        try:
            payload = build_revision_detail(store, query) if route.endswith("/revision") else build_lifecycle(store, query)
            return 200, payload
        except LifecycleError as error:
            status = 404 if error.kind == "not_found" else 400
            return status, {"error": error.kind, "reason": error.reason}
        except SelectionError as error:
            return 502, {
                "error": "lifecycle_read_failed",
                "operation": error.operation,
                "reason": "Agora could not read the requested lifecycle records.",
            }
        except GitReadError as error:
            return 502, {"error": "lifecycle_read_failed", "reason": str(error)}
    if method == "GET" and route == "/api/artifacts":
        if selection is None:
            return 409, {
                "error": "project_required",
                "reason": "Select a local Agora project before loading artifacts data.",
            }
        try:
            return 200, build_artifacts(store, query)
        except ArtifactsError as error:
            status = 404 if error.kind == "not_found" else 400
            return status, {"error": error.kind, "reason": error.reason}
        except SelectionError as error:
            return 502, {
                "error": "artifacts_read_failed",
                "operation": error.operation,
                "reason": "Agora could not read the requested artifacts, evidence, or approval records.",
            }
    if method == "POST" and route == "/api/projects/select":
        if not isinstance(payload, dict):
            return 400, {"error": "invalid_request", "reason": "the JSON body must be an object"}
        try:
            selected = store.select(payload.get("path"))
        except SelectionError as error:
            return 400, error.as_dict()
        return 200, {"status": "opened", "project": selected.as_dict()}
    return 404, {"error": "not_found"}


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
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urlsplit(self.path)
            route = parsed.path
            resolved = static_response(route)
            if resolved is not None:
                body, content_type, cache = resolved
                self._send_bytes(200, body, content_type, cache=cache)
                return
            if route.startswith("/assets/"):
                self._send_json(404, {"error": "not_found"})
                return
            query = parse_qs(parsed.query, keep_blank_values=True)
            status, payload = handle_api(self.server.store, "GET", route, query=query)
            self._send_json(status, payload)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            route = urlsplit(self.path).path
            if route != "/api/projects/select":
                status, payload = handle_api(self.server.store, "POST", route)
                self._send_json(status, payload)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "invalid_request", "reason": "invalid content length"})
                return
            if length <= 0 or length > 1_048_576:
                self._send_json(400, {"error": "invalid_request", "reason": "a JSON request body is required"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(400, {"error": "invalid_request", "reason": "the request body is not valid JSON"})
                return
            status, response = handle_api(self.server.store, "POST", route, payload)
            self._send_json(status, response)

        def log_message(self, format: str, *args: object) -> None:
            return

    return StudioHandler


def create_server(port: int = 7357, store: ProjectStore | None = None) -> StudioServer:
    if not 0 <= port <= 65535:
        raise StartupError(f"could not bind the local server: invalid port {port}")
    try:
        return StudioServer(("127.0.0.1", port), _handler(), store or ProjectStore())
    except OSError as error:
        raise StartupError(f"could not bind the local server on 127.0.0.1:{port}: {error}") from error


def server_url(server: StudioServer) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}"
