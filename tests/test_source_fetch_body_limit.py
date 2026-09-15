import unittest
from src.event_evidence import EventSource
from src.source_registry import AllowlistedSourceFetcher


SOURCE = EventSource("OFFICIAL", "https://official.example/", "OFFICIAL", 1)


class Resp:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return b"x" * 2_000_001
    def geturl(self): return SOURCE.url


class Opener:
    def open(self, request, timeout=15): return Resp()


class SourceBodyLimitTests(unittest.TestCase):
    def test_oversized_body_rejected(self):
        ok, ref = AllowlistedSourceFetcher((SOURCE,), Opener())(SOURCE)
        self.assertFalse(ok)
        self.assertEqual(ref, "")


if __name__ == "__main__":
    unittest.main()
