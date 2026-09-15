import unittest
from src.event_evidence import acquire_event_observation


class EmptyEventRegistryTests(unittest.TestCase):
    def test_empty_registry_is_unavailable(self):
        item = acquire_event_observation(lambda source: (True, "unexpected"), ())
        self.assertEqual(item.status, "UNAVAILABLE")
        self.assertEqual(item.source_ref, "")


if __name__ == "__main__":
    unittest.main()
