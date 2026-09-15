"""Idempotent D+1..D+5 checkpoint planning for 5DR V2.2.2.

Pure planning only: no database access and no market-evidence inference.
"""
from __future__ import annotations

from datetime import date, timedelta

CHECKPOINT_TYPES = ("D+1", "D+2", "D+3", "D+4", "D+5", "FINAL")


def _is_weekday(day: date) -> bool:
    return day.weekday() < 5


def next_trading_days(issuance_date: date, count: int = 5) -> list[date]:
    """Return weekday trading-day placeholders after issuance.

    Exchange holidays are intentionally not guessed here. A production caller
    must provide/verify the actual trading calendar before persistence.
    """
    days: list[date] = []
    cursor = issuance_date
    while len(days) < count:
        cursor += timedelta(days=1)
        if _is_weekday(cursor):
            days.append(cursor)
    return days


def plan_checkpoint_rows(*, forecast_id: str, issuance_date: date,
                         existing: set[tuple[str, date]] | None = None,
                         verified_trading_days: list[date] | None = None) -> list[dict]:
    """Plan missing checkpoint rows; fail closed without a verified calendar."""
    if not forecast_id:
        raise ValueError("forecast_id is required")
    if verified_trading_days is None:
        return []
    if len(verified_trading_days) < 5:
        raise ValueError("five verified trading days are required")
    days = verified_trading_days[:5]
    if days != sorted(days) or len(set(days)) != 5 or any(d <= issuance_date for d in days):
        raise ValueError("verified trading days must be five unique ascending dates after issuance")

    existing = existing or set()
    planned: list[dict] = []
    for idx, day in enumerate(days, start=1):
        checkpoint_type = f"D+{idx}"
        key = (checkpoint_type, day)
        if key not in existing:
            planned.append({
                "forecast_id": forecast_id,
                "checkpoint_type": checkpoint_type,
                "due_date": day,
                "status": "DUE",
            })
    final_key = ("FINAL", days[-1])
    if final_key not in existing:
        planned.append({
            "forecast_id": forecast_id,
            "checkpoint_type": "FINAL",
            "due_date": days[-1],
            "status": "DUE",
        })
    return planned
