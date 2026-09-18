import unittest
from datetime import date, datetime, timezone

from experiments.autonomous_schedule import (
    NSESessionCalendar,
    assess_schedule,
    run_key,
    validate_run_windows,
    watchdog_summary,
)
from experiments.data_contract import DataArchitectureError

WINDOWS = [
    {
        "label": "prior-close-refresh",
        "classification": "CANONICAL_CANDIDATE",
        "day_role": "PREVIOUS_TRADING_DAY",
        "start": "15:20:00",
        "end": "15:35:00",
    },
    {
        "label": "preopen-refresh",
        "classification": "CANONICAL_CANDIDATE",
        "day_role": "TARGET_TRADING_DAY",
        "start": "08:45:00",
        "end": "09:00:00",
    },
    {
        "label": "late-morning-snapshot",
        "classification": "INTRADAY_SNAPSHOT",
        "day_role": "TARGET_TRADING_DAY",
        "start": "10:25:00",
        "end": "10:40:00",
    },
]


class AutonomousScheduleTests(unittest.TestCase):
    def setUp(self):
        self.calendar = NSESessionCalendar(closed_dates={date(2026, 9, 14)})
        self.target = date(2026, 9, 15)

    def test_previous_trading_day_skips_weekend_and_explicit_holiday(self):
        self.assertEqual(self.calendar.previous_trading_day(self.target), date(2026, 9, 11))

    def test_due_window_is_executable_only_inside_bounded_window(self):
        now = datetime(2026, 9, 15, 3, 30, tzinfo=timezone.utc)  # 09:00 IST: end exclusive
        rows = assess_schedule(now, self.target, WINDOWS, calendar=self.calendar)
        preopen = next(row for row in rows if row["label"] == "PREOPEN-REFRESH")
        self.assertEqual(preopen["status"], "MISSED")
        self.assertFalse(preopen["execute_now"])
        self.assertFalse(preopen["late_execution_permitted"])

        inside = datetime(2026, 9, 15, 3, 25, tzinfo=timezone.utc)  # 08:55 IST
        rows = assess_schedule(inside, self.target, WINDOWS, calendar=self.calendar)
        preopen = next(row for row in rows if row["label"] == "PREOPEN-REFRESH")
        self.assertEqual(preopen["status"], "DUE")
        self.assertTrue(preopen["execute_now"])

    def test_idempotency_key_suppresses_duplicate_execution(self):
        key = run_key(self.target, "preopen-refresh")
        now = datetime(2026, 9, 15, 3, 25, tzinfo=timezone.utc)
        rows = assess_schedule(
            now, self.target, WINDOWS,
            calendar=self.calendar,
            completed_run_keys={key},
        )
        preopen = next(row for row in rows if row["run_key"] == key)
        self.assertEqual(preopen["status"], "COMPLETED")
        self.assertFalse(preopen["execute_now"])

    def test_watchdog_exposes_missed_run_instead_of_silent_catchup(self):
        now = datetime(2026, 9, 15, 5, 0, tzinfo=timezone.utc)  # 10:30 IST
        summary = watchdog_summary(now, self.target, WINDOWS, calendar=self.calendar)
        self.assertGreaterEqual(summary["missed_count"], 2)
        self.assertIn(run_key(self.target, "preopen-refresh"), summary["missed_run_keys"])
        self.assertIn(run_key(self.target, "late-morning-snapshot"), summary["due_run_keys"])

    def test_canonical_and_intraday_boundaries_are_frozen(self):
        with self.assertRaises(DataArchitectureError):
            validate_run_windows([{
                "label": "bad-prior",
                "classification": "CANONICAL_CANDIDATE",
                "day_role": "PREVIOUS_TRADING_DAY",
                "start": "15:19:00",
                "end": "15:30:00",
            }])
        with self.assertRaises(DataArchitectureError):
            validate_run_windows([{
                "label": "bad-preopen",
                "classification": "CANONICAL_CANDIDATE",
                "day_role": "TARGET_TRADING_DAY",
                "start": "09:00:00",
                "end": "09:16:00",
            }])
        with self.assertRaises(DataArchitectureError):
            validate_run_windows([{
                "label": "bad-intraday",
                "classification": "INTRADAY_SNAPSHOT",
                "day_role": "TARGET_TRADING_DAY",
                "start": "09:14:00",
                "end": "09:30:00",
            }])

    def test_special_open_date_can_override_weekend(self):
        saturday = date(2026, 9, 19)
        calendar = NSESessionCalendar(special_open_dates={saturday})
        self.assertTrue(calendar.is_trading_day(saturday))

    def test_naive_heartbeat_and_nontrading_target_fail_closed(self):
        with self.assertRaises(DataArchitectureError):
            assess_schedule(datetime(2026, 9, 15, 8, 55), self.target, WINDOWS, calendar=self.calendar)
        with self.assertRaises(DataArchitectureError):
            assess_schedule(
                datetime(2026, 9, 13, 3, 25, tzinfo=timezone.utc),
                date(2026, 9, 13), WINDOWS, calendar=self.calendar,
            )


if __name__ == "__main__":
    unittest.main()
