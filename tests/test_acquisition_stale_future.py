import unittest
from datetime import datetime, timedelta, timezone
from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation


class FutureEvidenceTests(unittest.TestCase):
    def test_materially_future_timestamp_blocks(self):
        now = datetime.now(timezone.utc)
        item = SourceObservation("MARKET_TRUST", "source:future", (now + timedelta(minutes=5)).isoformat())
        with self.assertRaisesRegex(AcquisitionBlocked, "STALE_EVIDENCE"):
            item.validate(now)


if __name__ == "__main__":
    unittest.main()
