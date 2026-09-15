import unittest
from src.event_evidence import acquire_event_observation


class EventFailureLanguageTests(unittest.TestCase):
    def test_failure_never_claims_no_event(self):
        item = acquire_event_observation(lambda source: (False, ""))
        self.assertEqual(item.status, "UNAVAILABLE")
        self.assertNotEqual(item.detail.lower().strip(), "no event")
        self.assertIn("do not infer", item.detail.lower())


if __name__ == "__main__":
    unittest.main()
