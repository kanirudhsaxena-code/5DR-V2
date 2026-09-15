import unittest

from src.event_evidence import EventSource, acquire_event_observation


SOURCES = (
    EventSource("PRIMARY", "https://primary.invalid/", "OFFICIAL", 1),
    EventSource("FALLBACK", "https://fallback.invalid/", "SECONDARY", 2),
)


class EventEvidenceTests(unittest.TestCase):
    def test_primary_success_verified(self):
        item = acquire_event_observation(lambda source: (True, "web://primary#digest") if source.name == "PRIMARY" else (False, ""), SOURCES)
        self.assertEqual(item.status, "VERIFIED")
        self.assertFalse(item.fallback_used)

    def test_fallback_is_explicitly_degraded(self):
        item = acquire_event_observation(lambda source: (source.name == "FALLBACK", "web://fallback#digest" if source.name == "FALLBACK" else ""), SOURCES)
        self.assertEqual(item.status, "DEGRADED")
        self.assertTrue(item.fallback_used)

    def test_total_failure_is_unavailable_not_no_event(self):
        item = acquire_event_observation(lambda source: (False, ""), SOURCES)
        self.assertEqual(item.status, "UNAVAILABLE")
        self.assertIn("do not infer absence", item.detail)


if __name__ == "__main__":
    unittest.main()
