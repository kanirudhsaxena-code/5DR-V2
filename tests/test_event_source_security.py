import unittest

from src.event_evidence import DEFAULT_EVENT_SOURCES


class EventSourceSecurityTests(unittest.TestCase):
    def test_registry_is_https_and_unique(self):
        urls = [s.url for s in DEFAULT_EVENT_SOURCES]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all(url.startswith("https://") for url in urls))
        self.assertTrue(all(s.priority > 0 for s in DEFAULT_EVENT_SOURCES))


if __name__ == "__main__":
    unittest.main()
