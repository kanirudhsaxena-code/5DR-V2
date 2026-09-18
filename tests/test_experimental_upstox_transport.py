import subprocess
import unittest
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request

from experiments.upstox_transport import CurlOpener


SECRET = "test-secret-must-never-appear-in-argv"
URL = "https://api.upstox.com/v3/market-quote/ltp?instrument_key=NSE_INDEX%7CNifty%2050"
MARKER = b"\n__5DR_HTTP_STATUS__="


class CurlTransportTests(unittest.TestCase):
    def test_get_only_no_redirect_and_secret_not_in_argv(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["input"] = kwargs["input"]
            return SimpleNamespace(returncode=0, stdout=b'{"status":"success","data":{}}' + MARKER + b"200", stderr=b"")

        request = Request(
            URL,
            headers={"Accept": "application/json", "Authorization": "Bearer " + SECRET},
            method="GET",
        )
        with CurlOpener(runner=fake_run).open(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'"status":"success"', response.read())

        argv = captured["command"]
        self.assertNotIn(SECRET, " ".join(argv))
        self.assertNotIn("-L", argv)
        self.assertNotIn("--location", argv)
        self.assertIn("--header", argv)
        self.assertIn("@-", argv)
        self.assertIn(SECRET.encode(), captured["input"])

    def test_non_get_fails_closed_before_subprocess(self):
        called = []

        def fake_run(*args, **kwargs):
            called.append(True)
            raise AssertionError("runner must not be called")

        request = Request(URL, data=b"x", method="POST")
        with self.assertRaises(URLError):
            CurlOpener(runner=fake_run).open(request)
        self.assertFalse(called)

    def test_http_error_is_preserved_for_existing_client(self):
        def fake_run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout=b'{"errors":[{"errorCode":"UDAPI100050"}]}' + MARKER + b"403", stderr=b"")

        request = Request(URL, method="GET")
        with self.assertRaises(HTTPError) as caught:
            CurlOpener(runner=fake_run).open(request)
        self.assertEqual(caught.exception.code, 403)

    def test_missing_status_marker_fails_closed(self):
        def fake_run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout=b"unexpected", stderr=b"")

        with self.assertRaises(URLError):
            CurlOpener(runner=fake_run).open(Request(URL, method="GET"))

    def test_timeout_or_curl_failure_does_not_expose_stderr(self):
        def fake_run(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 3, stderr=("Bearer " + SECRET).encode())

        with self.assertRaises(URLError) as caught:
            CurlOpener(runner=fake_run).open(Request(URL, method="GET"), timeout=3)
        self.assertNotIn(SECRET, str(caught.exception))

    def test_body_over_limit_fails_closed(self):
        def fake_run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout=b"123456" + MARKER + b"200", stderr=b"")

        with self.assertRaises(URLError):
            CurlOpener(runner=fake_run, max_bytes=5).open(Request(URL, method="GET"))


if __name__ == "__main__":
    unittest.main()
