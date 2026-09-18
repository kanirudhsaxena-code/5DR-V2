import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from experiments.run_upstox_reliability_burst import checkpoint_datetimes


class BurstScheduleTests(unittest.TestCase):
    def test_four_expected_market_open_checkpoints(self):
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime(2026, 9, 16, 8, 30, tzinfo=ist)
        values = checkpoint_datetimes(now)
        self.assertEqual([value.strftime("%H:%M") for value in values], ["09:45", "10:00", "10:15", "10:30"])

    def test_checkpoint_dates_stay_on_same_ist_day(self):
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime(2026, 9, 16, 9, 50, tzinfo=ist)
        values = checkpoint_datetimes(now)
        self.assertTrue(all(value.date() == now.date() for value in values))
        self.assertTrue(all(value.tzinfo == ist for value in values))


if __name__ == "__main__":
    unittest.main()
