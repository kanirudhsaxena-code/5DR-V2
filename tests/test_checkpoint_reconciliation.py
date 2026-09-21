from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.checkpoint_reconciliation import (
    IST,
    checkpoint_is_capture_eligible,
    exact_daily_candle,
)


class FakeDailyClient:
    def daily(self, start, end):
        assert start == end == date(2026, 9, 18)
        return {
            "sha256": "a" * 64,
            "payload": {
                "data": {
                    "candles": [
                        # Upstox daily bars can be stamped at the UTC instant
                        # corresponding to the Indian session date boundary.
                        ["2026-09-17T18:30:00+00:00", 23300.0, 23400.0, 23200.0, 23346.4, 1000, 0]
                    ]
                }
            },
        }


def test_same_day_checkpoint_waits_until_post_close():
    before = datetime(2026, 9, 21, 15, 30, tzinfo=IST)
    after = datetime(2026, 9, 21, 15, 45, tzinfo=IST)
    assert checkpoint_is_capture_eligible(date(2026, 9, 21), before) is False
    assert checkpoint_is_capture_eligible(date(2026, 9, 21), after) is True


def test_prior_trading_date_is_always_capture_eligible():
    now = datetime(2026, 9, 21, 9, 30, tzinfo=IST)
    assert checkpoint_is_capture_eligible(date(2026, 9, 18), now) is True


def test_exact_daily_candle_maps_provider_timestamp_to_ist_session_date():
    candle = exact_daily_candle(FakeDailyClient(), date(2026, 9, 18))
    assert candle["trading_date"] == date(2026, 9, 18)
    assert candle["close"] == 23346.4
    assert candle["high"] == 23400.0
    assert candle["low"] == 23200.0
    assert candle["source_ref"].startswith("UPSTOX_AUTHENTICATED:NIFTY_DAILY:2026-09-18:")


def test_exact_daily_candle_fails_closed_for_wrong_session():
    class WrongDay(FakeDailyClient):
        def daily(self, start, end):
            env = super().daily(start, end)
            env["payload"]["data"]["candles"][0][0] = "2026-09-16T18:30:00+00:00"
            return env

    try:
        exact_daily_candle(WrongDay(), date(2026, 9, 18))
        assert False, "wrong session candle must not be accepted"
    except ValueError as exc:
        assert "not available" in str(exc)
