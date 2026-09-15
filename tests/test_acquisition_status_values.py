import unittest
from src.autonomous_acquisition import SourceObservation
from datetime import datetime, timezone


class AcquisitionStatusTests(unittest.TestCase):
    def test_invalid_status_rejected(self):
        item = SourceObservation("MARKET_TRUST", "source:x", datetime.now(timezone.utc).isoformat(), status="MAGIC_READY")
        with self.assertRaisesRegex(Exception, "INVALID_STATUS"):
            item.validate(datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
