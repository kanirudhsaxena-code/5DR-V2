import unittest

from experiments.live_shadow_bundle import _merge_candles, _series_digest, _stamp


class LiveShadowBundlePureTests(unittest.TestCase):
    def test_merge_candles_deduplicates_by_provider_timestamp(self):
        old = [["2026-09-16T09:15:00+05:30", 100, 102, 99, 101, 0, 0]]
        new = [["2026-09-16T09:15:00+05:30", 100, 103, 99, 102, 0, 0], ["2026-09-16T09:20:00+05:30", 102, 104, 101, 103, 0, 0]]
        merged = _merge_candles(old, new)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0][4], 102)

    def test_series_digest_changes_with_market_content(self):
        one = [["2026-09-16T09:15:00+00:00", 1, 2, 1, 2, 0, 0]]
        two = [["2026-09-16T09:15:00+00:00", 1, 3, 1, 2, 0, 0]]
        self.assertNotEqual(_series_digest(one), _series_digest(two))

    def test_epoch_and_iso_timestamp_normalize_to_aware_utc(self):
        self.assertIsNotNone(_stamp("2026-09-16T09:15:00+05:30").tzinfo)
        self.assertIsNotNone(_stamp(1789521300000).tzinfo)


if __name__ == "__main__":
    unittest.main()
