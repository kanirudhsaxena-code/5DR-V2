import unittest
from src.event_evidence import EventSource, acquire_event_observation


class RegistryFallbackAuthorityTests(unittest.TestCase):
    def test_fallback_authority_is_recorded(self):
        sources = (EventSource("A", "https://a.example/", "OFFICIAL", 1), EventSource("B", "https://b.example/", "EXCHANGE", 2))
        item = acquire_event_observation(lambda s: (s.name == "B", "web:b" if s.name == "B" else ""), sources)
        self.assertEqual(item.status, "DEGRADED")
        self.assertEqual(item.authority, "EXCHANGE")
        self.assertTrue(item.fallback_used)


if __name__ == "__main__":
    unittest.main()
