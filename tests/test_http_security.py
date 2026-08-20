from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest

from agora_studio.core import ProjectStore
from agora_studio.server import create_server
from tests.support import FakeGateway


class NoopCommands:
    def approve_gate(self, *args, **kwargs):
        raise AssertionError("command gateway was not expected")


class HttpSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.server = create_server(
            0,
            ProjectStore(FakeGateway()),
            NoopCommands(),
            csrf_token="test-csrf-token",
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.directory.cleanup()

    def request(self, method: str, path: str, body: bytes | None = None, **headers: str):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers.setdefault("Host", f"127.0.0.1:{self.port}")
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        result = response.status, payload, dict(response.getheaders())
        connection.close()
        return result

    def mutation_headers(self) -> dict[str, str]:
        return {
            "Origin": f"http://127.0.0.1:{self.port}",
            "X-Agora-Studio-CSRF": "test-csrf-token",
            "Content-Type": "application/json",
        }

    def test_project_bootstrap_exposes_process_token_and_security_headers(self) -> None:
        status, payload, headers = self.request("GET", "/api/v1/project")
        self.assertEqual(status, 200)
        self.assertEqual(payload["csrf_token"], "test-csrf-token")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_rejects_invalid_host_origin_and_csrf(self) -> None:
        status, payload, _ = self.request("GET", "/api/v1/project", Host="attacker.invalid")
        self.assertEqual((status, payload["error"]), (421, "invalid_host"))

        body = json.dumps({"path": self.directory.name}).encode()
        headers = self.mutation_headers()
        headers["Origin"] = "https://attacker.invalid"
        status, payload, _ = self.request("POST", "/api/v1/projects/select", body, **headers)
        self.assertEqual((status, payload["error"]), (403, "invalid_origin"))

        headers = self.mutation_headers()
        headers["X-Agora-Studio-CSRF"] = "wrong"
        status, payload, _ = self.request("POST", "/api/v1/projects/select", body, **headers)
        self.assertEqual((status, payload["error"]), (403, "csrf_rejected"))

    def test_enforces_json_content_type_and_body_limit(self) -> None:
        body = json.dumps({"path": self.directory.name}).encode()
        headers = self.mutation_headers()
        headers["Content-Type"] = "text/plain"
        status, payload, _ = self.request("POST", "/api/v1/projects/select", body, **headers)
        self.assertEqual((status, payload["error"]), (415, "invalid_request"))

        headers = self.mutation_headers()
        headers["Content-Length"] = "65537"
        status, payload, _ = self.request("POST", "/api/v1/projects/select", body, **headers)
        self.assertEqual((status, payload["error"]), (413, "invalid_request"))

    def test_valid_same_origin_selection_succeeds(self) -> None:
        body = json.dumps({"path": self.directory.name}).encode()
        status, payload, _ = self.request(
            "POST", "/api/v1/projects/select", body, **self.mutation_headers()
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema"], "agora-studio/api/project-opened/v1")


if __name__ == "__main__":
    unittest.main()
