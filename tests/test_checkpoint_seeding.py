from datetime import date

import pytest

from src.checkpoint_seeding import plan_checkpoint_rows


def test_no_verified_calendar_means_no_rows():
    assert plan_checkpoint_rows(forecast_id="F1", issuance_date=date(2026, 9, 15)) == []


def test_plans_d1_to_d5_and_final_from_verified_calendar():
    days = [date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 18), date(2026, 9, 21), date(2026, 9, 22)]
    rows = plan_checkpoint_rows(forecast_id="F1", issuance_date=date(2026, 9, 15), verified_trading_days=days)
    assert [r["checkpoint_type"] for r in rows] == ["D+1", "D+2", "D+3", "D+4", "D+5", "FINAL"]
    assert rows[-1]["due_date"] == date(2026, 9, 22)
    assert all(r["status"] == "DUE" for r in rows)


def test_existing_rows_are_not_replanned():
    days = [date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 18), date(2026, 9, 21), date(2026, 9, 22)]
    existing = {("D+1", days[0]), ("FINAL", days[-1])}
    rows = plan_checkpoint_rows(forecast_id="F1", issuance_date=date(2026, 9, 15), existing=existing, verified_trading_days=days)
    assert [r["checkpoint_type"] for r in rows] == ["D+2", "D+3", "D+4", "D+5"]


def test_rejects_invalid_verified_calendar():
    with pytest.raises(ValueError):
        plan_checkpoint_rows(forecast_id="F1", issuance_date=date(2026, 9, 15), verified_trading_days=[date(2026, 9, 16)] * 5)
