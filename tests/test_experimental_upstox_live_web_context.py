import hashlib
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError

from experiments.data_contract import DataArchitectureError
from experiments.live_web_context import ROLE_SOURCES, collect_live_web_context


class FakeResponse:
    def __init__(self, body):
        self._body = body
    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, bodies=None, failing_urls=None):
        self.bodies = bodies or {}
        self.failing_urls = set(failing_urls or ())
        self.calls = []
    def open(self, request, timeout=20):
        url = request.full_url
        self.calls.append((request.get_method(), url, timeout))
        if url in self.failing_urls:
            raise HTTPError(url, 503, "blocked", None, None)
        return FakeResponse(self.bodies[url])


def html_for(role):
    keywords = " ".join(role.keywords)
    return f"<html><head><title>{role.role}</title></head><body><h1>{keywords}</h1><p>{'context ' * 40}</p></body></html>".encode()


def opener_for_all():
    bodies = {}
    for role in ROLE_SOURCES:
        for url in role.urls:
            bodies[url] = html_for(role)
    return FakeOpener(bodies=bodies)


class LiveWebContextTests(unittest.TestCase):
    def test_all_required_roles_produce_hashed_bounded_context(self):
        now = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)
        result = collect_live_web_context(now=now, opener=opener_for_all())
        self.assertEqual(result["status"], "5DR_LIVE_WEB_CONTEXT_PASSED")
        self.assertEqual(set(result["roles"]), {r.role for r in ROLE_SOURCES})
        self.assertEqual(len(result["items"]), len(ROLE_SOURCES))
        self.assertFalse(result["screenshot_required"])
        self.assertFalse(result["forecast_released"])
        self.assertFalse(result["production_5dr_write_enabled"])
        for item in result["items"]:
            self.assertEqual(item["validation_status"], "VALID")
            self.assertEqual(len(item["source_sha256"]), 64)
            self.assertIn("role=", item["fact_summary"])

    def test_missing_required_role_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            collect_live_web_context(
                now=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
                opener=opener_for_all(),
                roles=ROLE_SOURCES[:-1],
            )

    def test_keyword_mismatch_blocks_wrong_page(self):
        role = ROLE_SOURCES[0]
        bodies = {url: b"<html><body>unrelated page text " + b"x" * 200 + b"</body></html>" for url in role.urls}
        opener = FakeOpener(bodies=bodies)
        with self.assertRaises(DataArchitectureError):
            collect_live_web_context(
                now=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
                opener=opener,
                roles=(role,) + ROLE_SOURCES[1:],
            )

    def test_fallback_url_is_used_only_after_primary_failure(self):
        role = next(r for r in ROLE_SOURCES if len(r.urls) > 1)
        bodies = {url: html_for(role) for url in role.urls}
        # Other roles must also be available.
        for other in ROLE_SOURCES:
            for url in other.urls:
                bodies.setdefault(url, html_for(other))
        opener = FakeOpener(bodies=bodies, failing_urls={role.urls[0]})
        result = collect_live_web_context(
            now=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
            opener=opener,
        )
        item = next(i for i in result["items"] if f"role={role.role};" in i["fact_summary"])
        self.assertEqual(item["source_reference"], role.urls[1])

    def test_only_get_requests_are_issued(self):
        opener = opener_for_all()
        collect_live_web_context(
            now=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
            opener=opener,
        )
        self.assertTrue(opener.calls)
        self.assertTrue(all(method == "GET" for method, _, _ in opener.calls))


if __name__ == "__main__":
    unittest.main()
