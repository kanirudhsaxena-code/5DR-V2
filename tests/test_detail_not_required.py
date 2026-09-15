import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation


class DetailOptionalTests(unittest.TestCase):
    def test_verified_observation_does_not_require_detail(self):
        now = datetime.now(timezone.utc)
        SourceObservation("MARKET_TRUST", "source:verified", now.isoformat()).validate(now)


if __name__ == "__main__":
    unittest.main()
