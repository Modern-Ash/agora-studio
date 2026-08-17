"""Loopback-only HTTP interface for Agora Studio."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit

from .core import ProjectStore, SelectionError


class StartupError(Exception):
    """The local server could not bind safely."""


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], store: ProjectStore):
        self.store = store
        super().__init__(server_address, handler)


def handle_api(
    store: ProjectStore,
    method: str,
    route: str,
    payload: object | None = None,
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

        def _send(self, status: int, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            route = urlsplit(self.path).path
            status, payload = handle_api(self.server.store, "GET", route)
            self._send(status, payload)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            route = urlsplit(self.path).path
            if route != "/api/projects/select":
                status, payload = handle_api(self.server.store, "POST", route)
                self._send(status, payload)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"error": "invalid_request", "reason": "invalid content length"})
                return
            if length <= 0 or length > 1_048_576:
                self._send(400, {"error": "invalid_request", "reason": "a JSON request body is required"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, {"error": "invalid_request", "reason": "the request body is not valid JSON"})
                return
            status, response = handle_api(self.server.store, "POST", route, payload)
            self._send(status, response)

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
