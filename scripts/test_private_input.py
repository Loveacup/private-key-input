import importlib.util
import json
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

    def test_callback_failure_closes_server(self):
        def fail(value):
            raise RuntimeError("synthetic failure")
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


if __name__ == "__main__":
    unittest.main()
