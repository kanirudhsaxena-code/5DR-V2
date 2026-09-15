import io
import unittest

from src.event_evidence import EventSource
from src.source_registry import AllowlistedSourceFetcher


SOURCE = EventSource("OFFICIAL", "https://official.example/", "OFFICIAL", 1)


class FakeResponse:
    def __init__(self, body=b"verified", url=SOURCE.url):
        self.body, self.url = body, url
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.body
    def geturl(self): return self.url


class FakeOpener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout=15): return self.response


class SourceRegistryTests(unittest.TestCase):
    def test_allowlisted_source_gets_hashed_reference(self):
        fetch = AllowlistedSourceFetcher((SOURCE,), FakeOpener(FakeResponse()))
        ok, ref = fetch(SOURCE)
        self.assertTrue(ok)
        self.assertTrue(ref.startswith("web:https://official.example/#sha256="))

    def test_unregistered_source_is_rejected_without_network(self):
        fetch = AllowlistedSourceFetcher((SOURCE,), FakeOpener(FakeResponse()))
        ok, ref = fetch(EventSource("OTHER", "https://other.example/", "SECONDARY", 2))
        self.assertFalse(ok)
        self.assertEqual(ref, "")

    def test_redirect_is_rejected(self):
        fetch = AllowlistedSourceFetcher((SOURCE,), FakeOpener(FakeResponse(url="https://redirect.example/")))
        ok, ref = fetch(SOURCE)
        self.assertFalse(ok)
        self.assertEqual(ref, "")


if __name__ == "__main__":
    unittest.main()
