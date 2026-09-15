import unittest
from src.event_evidence import DEFAULT_EVENT_SOURCES


class SourceAuthorityTests(unittest.TestCase):
    def test_official_sources_precede_exchange_fallback(self):
        official = [s for s in DEFAULT_EVENT_SOURCES if s.authority == "OFFICIAL_REGULATORY"]
        exchange = [s for s in DEFAULT_EVENT_SOURCES if s.authority == "EXCHANGE"]
        self.assertTrue(official and exchange)
        self.assertLessEqual(max(s.priority for s in official), min(s.priority for s in exchange))


if __name__ == "__main__":
    unittest.main()
