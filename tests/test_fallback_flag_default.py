import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation


class FallbackDefaultTests(unittest.TestCase):
    def test_default_is_false(self):
        item = SourceObservation("MARKET_TRUST", "source:x", datetime.now(timezone.utc).isoformat())
        self.assertFalse(item.fallback_used)


if __name__ == "__main__":
    unittest.main()
