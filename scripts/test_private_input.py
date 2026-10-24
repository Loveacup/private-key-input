import importlib.util
import json
import socket
import contextlib
import io
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("private_input", Path(__file__).with_name("private_input.py"))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PrivateInputTest(unittest.TestCase):
    def start(self, callback=lambda value: None, **kwargs):
        server = mod.InputServer(callback, "Synthetic test", ttl=3, **kwargs)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        return server, thread

    def request(self, request):
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, exc.read().decode()

    def test_page_and_one_time_submit(self):
        received = []
        server, thread = self.start(received.append)
        status, page = self.request(urllib.request.Request(server.url))
        self.assertEqual(status, 200)
        self.assertNotIn("synthetic-secret", page)
        body = json.dumps({"secret": "synthetic-secret"}).encode()
        request = urllib.request.Request(server.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Origin": server.origin,
            "X-Input-Token": server.token,
        })
        status, response = self.request(request)
        thread.join(2)
        self.assertEqual(status, 200)
        self.assertEqual(received, ["synthetic-secret"])
        self.assertEqual(server.outcome, "submitted")
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(server.url, timeout=1)

    def test_wrong_origin_rejected(self):
        server, thread = self.start()
        body = json.dumps({"secret": "synthetic-secret"}).encode()
        request = urllib.request.Request(server.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Origin": "http://invalid.test",
            "X-Input-Token": server.token,
        })
        status, _ = self.request(request)
        self.assertEqual(status, 403)
        server.outcome = "cancelled"
        thread.join(2)

    def test_expiry(self):
        server = mod.InputServer(lambda value: None, "test", ttl=0.05)
        self.assertEqual(server.run(), "expired")

    def test_wrong_token_and_route(self):
        server, thread = self.start()
        status, _ = self.request(urllib.request.Request(server.origin + "/"))
        self.assertEqual(status, 404)
        request = urllib.request.Request(server.url, data=b'{"secret":"synthetic"}', headers={
            "Content-Type": "application/json", "Origin": server.origin,
            "X-Input-Token": "wrong",
        })
        status, _ = self.request(request)
        self.assertEqual(status, 403)
        server.outcome = "cancelled"
        thread.join(2)

    def test_plain_lan_requires_explicit_consent(self):
        with self.assertRaises(ValueError):
            mod.InputServer(lambda value: None, "test", host="0.0.0.0", public_origin="http://192.0.2.1:8080")

    def test_late_body_is_not_processed_after_deadline(self):
        received = []
        server = mod.InputServer(received.append, "test", ttl=0.3)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        conn = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        body = json.dumps({"secret": "synthetic-secret"}).encode()
        headers = (f"POST {server.route} HTTP/1.1\r\nHost: {server.host_header}\r\n"
                   f"Origin: {server.origin}\r\nX-Input-Token: {server.token}\r\n"
                   f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n")
        conn.sendall(headers.encode())
        time.sleep(0.4)
        try:
            conn.sendall(body)
        except OSError:
            pass  # An already closed expired connection is expected.
        conn.close()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(received, [])
        self.assertEqual(server.outcome, "expired")

    def test_partial_request_does_not_hold_server_past_deadline(self):
        server = mod.InputServer(lambda value: None, "test", ttl=0.3)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        conn = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        conn.sendall(b"GET / HTTP/1.1\r\n")
        thread.join(1)
        conn.close()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(server.outcome, "expired")

    def test_callback_failure_closes_server(self):
        def fail(value):
            raise RuntimeError("synthetic-secret")
        output = io.StringIO()
        capture = contextlib.ExitStack()
        capture.enter_context(contextlib.redirect_stdout(output))
        capture.enter_context(contextlib.redirect_stderr(output))
        self.addCleanup(capture.close)
        server, thread = self.start(fail)
        body = json.dumps({"secret": "synthetic-secret"}).encode()
        request = urllib.request.Request(server.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Origin": server.origin,
            "X-Input-Token": server.token,
        })
        status, response = self.request(request)
        thread.join(2)
        self.assertEqual(status, 500)
        self.assertNotIn("synthetic-secret", response)
        self.assertEqual(server.outcome, "handler_failed")
        capture.close()
        self.assertNotIn("synthetic-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
