"""SQL generation for append-only V2.2.2 lifecycle persistence.

The production caller executes these statements only after evidence validation.
All writes are idempotent and historical rows are never updated/deleted.
"""
from __future__ import annotations

ALLOWED_EVENTS = {"MARK", "T1_HIT", "T2_HIT", "SL_HIT", "THESIS_EXIT", "TIME_EXIT", "NOT_SCORABLE"}


def recommendation_event_insert(event_type: str) -> str:
    if event_type not in ALLOWED_EVENTS:
        raise ValueError("unsupported autonomous event")
    return """
INSERT INTO recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT %(forecast_id)s,%(event_type)s,%(event_timestamp)s,%(premium)s,%(pnl_pct)s,%(r_multiple)s,%(source_ref)s,%(notes)s
WHERE NOT EXISTS (
  SELECT 1 FROM recommendation_events
  WHERE forecast_id=%(forecast_id)s AND event_type=%(event_type)s
    AND event_timestamp=%(event_timestamp)s
    AND premium IS NOT DISTINCT FROM %(premium)s
);
""".strip()


def checkpoint_capture_sql() -> str:
    return """
UPDATE outcome_checkpoints
SET status='CAPTURED', observed_at=%(observed_at)s, actual_nifty=%(actual_nifty)s,
    period_high=%(period_high)s, period_low=%(period_low)s,
    option_premium=%(option_premium)s, source_ref=%(source_ref)s, notes=%(notes)s
WHERE checkpoint_id=%(checkpoint_id)s AND status='DUE';
""".strip()


def assert_append_only_event_sql(sql: str) -> None:
    normalized = sql.upper()
    if "UPDATE RECOMMENDATION_EVENTS" in normalized or "DELETE FROM RECOMMENDATION_EVENTS" in normalized:
        raise ValueError("recommendation_events is append-only")
