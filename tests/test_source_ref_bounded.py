import unittest
from datetime import datetime, timezone

from src.autonomous_acquisition import SourceObservation


class SourceReferenceTests(unittest.TestCase):
    def test_normal_provenance_reference_validates(self):
        item = SourceObservation("MARKET_TRUST", "upstox:/v3/path#sha256=" + "a" * 64, datetime.now(timezone.utc).isoformat())
        item.validate(datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
