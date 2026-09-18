import unittest
from datetime import datetime, timedelta, timezone

from experiments.chart_structure import (
    anchored_vwap,
    derive_chart_evidence,
    derive_multi_timeframe_evidence,
)
from experiments.data_contract import DataArchitectureError


def rows_from_ohlc(values, *, volumes=None, start=None):
    start = start or datetime(2026, 9, 15, 3, 45, tzinfo=timezone.utc)
    volumes = volumes if volumes is not None else [0] * len(values)
    rows = []
    for index, ((open_, high, low, close), volume) in enumerate(zip(values, volumes)):
        stamp = (start + timedelta(minutes=5 * index)).isoformat()
        rows.append([stamp, open_, high, low, close, volume, 0])
    return rows


UP = rows_from_ohlc([
    (100, 105, 95, 101),
    (108, 115, 105, 110),
    (105, 110, 100, 105),
    (118, 125, 110, 120),
    (112, 118, 106, 112),
    (128, 135, 120, 130),
    (120, 128, 115, 120),
    (134, 140, 123, 136),
    (125, 134, 118, 125),
])

DOWN = rows_from_ohlc([
    (140, 145, 135, 139),
    (130, 140, 125, 130),
    (134, 142, 130, 134),
    (120, 132, 115, 120),
    (125, 136, 120, 125),
    (110, 120, 105, 110),
    (112, 128, 110, 112),
    (100, 110, 95, 100),
    (104, 118, 100, 104),
])


class ChartStructureTests(unittest.TestCase):
    def test_higher_high_higher_low_structure_is_derived_without_scoring(self):
        evidence = derive_chart_evidence(UP, "1h", swing_radius=1, breakout_lookback=4)
        self.assertEqual(evidence["trend_structure"]["state"], "UPTREND_STRUCTURE")
        self.assertEqual(evidence["trend_structure"]["high_sequence"], "HH")
        self.assertEqual(evidence["trend_structure"]["low_sequence"], "HL")
        self.assertFalse(evidence["directional_score_assigned"])
        self.assertFalse(evidence["forecast_released"])

    def test_lower_high_lower_low_structure_is_derived(self):
        evidence = derive_chart_evidence(DOWN, "30m", swing_radius=1, breakout_lookback=4)
        self.assertEqual(evidence["trend_structure"]["state"], "DOWNTREND_STRUCTURE")
        self.assertEqual(evidence["trend_structure"]["high_sequence"], "LH")
        self.assertEqual(evidence["trend_structure"]["low_sequence"], "LL")

    def test_liquidity_sweep_is_close_sensitive_not_just_intrabar_break(self):
        base = rows_from_ohlc([
            (100, 105, 95, 101),
            (101, 106, 98, 103),
            (103, 108, 100, 105),
            (105, 110, 102, 107),
            (107, 109, 103, 106),
            (106, 112, 104, 108),
        ])
        evidence = derive_chart_evidence(base, "15m", swing_radius=1, breakout_lookback=5)
        self.assertEqual(evidence["range_event"]["liquidity_sweep"], "UPSIDE_LIQUIDITY_SWEEP")
        self.assertEqual(evidence["range_event"]["close_state"], "CLOSE_INSIDE_PRIOR_RANGE")

    def test_true_close_breakout_is_distinct_from_sweep(self):
        base = rows_from_ohlc([
            (100, 105, 95, 101),
            (101, 106, 98, 103),
            (103, 108, 100, 105),
            (105, 110, 102, 107),
            (107, 109, 103, 106),
            (108, 114, 107, 113),
        ])
        evidence = derive_chart_evidence(base, "15m", swing_radius=1, breakout_lookback=5)
        self.assertEqual(evidence["range_event"]["close_state"], "CLOSE_ABOVE_PRIOR_RANGE")
        self.assertEqual(evidence["range_event"]["liquidity_sweep"], "NONE")

    def test_zero_index_volume_cannot_create_fake_vwap_or_volume_confirmation(self):
        evidence = derive_chart_evidence(UP, "1d", swing_radius=1, breakout_lookback=4)
        self.assertEqual(evidence["anchored_vwap_from_first_bar"]["status"], "VOLUME_UNAVAILABLE")
        self.assertEqual(evidence["volume_confirmation"]["status"], "VOLUME_NOT_APPLICABLE_OR_UNAVAILABLE")

    def test_positive_futures_style_volume_can_compute_vwap(self):
        volumes = [100, 120, 110, 150, 140, 180, 160, 200, 170]
        rows = rows_from_ohlc([row[1:5] for row in UP], volumes=volumes)
        result = anchored_vwap(rows)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertGreater(result["value"], 0)
        self.assertEqual(result["bars_used"], len(rows))

    def test_gap_is_detected_from_nonoverlapping_candle_ranges(self):
        data = rows_from_ohlc([
            (100, 105, 95, 102),
            (103, 108, 100, 105),
            (112, 118, 111, 115),
            (114, 119, 112, 118),
            (118, 121, 115, 119),
        ])
        evidence = derive_chart_evidence(data, "1d", swing_radius=1, breakout_lookback=3)
        self.assertTrue(any(gap["direction"] == "GAP_UP" for gap in evidence["recent_gaps"]))

    def test_multi_timeframe_alignment_excludes_five_minute_direction_from_directional_alignment(self):
        combined = derive_multi_timeframe_evidence(
            {"1d": UP, "1h": UP, "15m": UP, "5m": DOWN},
            swing_radius=1,
            breakout_lookback=4,
        )
        self.assertEqual(combined["directional_alignment_excluding_5m"], "ALIGNED_UP")
        self.assertTrue(combined["timeframes"]["5m"]["execution_only"])
        self.assertTrue(combined["five_minute_execution_only"])

    def test_duplicate_or_naive_timestamps_fail_closed(self):
        duplicate = [list(row) for row in UP]
        duplicate[-1][0] = duplicate[-2][0]
        with self.assertRaises(DataArchitectureError):
            derive_chart_evidence(duplicate, "1h", swing_radius=1, breakout_lookback=4)
        naive = [list(row) for row in UP]
        naive[0][0] = "2026-09-15T09:15:00"
        with self.assertRaises(DataArchitectureError):
            derive_chart_evidence(naive, "1h", swing_radius=1, breakout_lookback=4)

    def test_unsupported_timeframe_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            derive_chart_evidence(UP, "2h", swing_radius=1, breakout_lookback=4)


if __name__ == "__main__":
    unittest.main()
