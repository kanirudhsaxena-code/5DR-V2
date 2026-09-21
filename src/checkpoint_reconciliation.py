"""Automated reconciliation of due canonical 5DR D+1..D+5 checkpoints.

Uses authenticated read-only Upstox NIFTY daily candles to capture realized index
OHLC for due trading dates. It never reconstructs or invents a missing frozen
forecast. Checkpoints with missing daily_forecast context are captured for audit
but remain unscored until the original immutable forecast path is recovered.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from phase1.upstox import ReadOnlyClient, validate_candles
from experiments.upstox_transport import CurlOpener
from .assessment import evaluate_forecast_checkpoint
from .console_forecast_sync import next_trading_days_after

IST = ZoneInfo("Asia/Kolkata")
POST_CLOSE_CAPTURE = time(15, 40)
PRIMARY = {f"D+{day}": day for day in range(1, 6)}


@dataclass(frozen=True)
class ReconciliationSummary:
    seeded_checkpoints: int
    due_seen: int
    eligible_seen: int
    captured: int
    evaluated: int
    already_evaluated: int
    missing_frozen_forecast: int
    not_yet_due: int
    source_failures: int

    def to_dict(self) -> dict:
        return asdict(self)


def checkpoint_is_capture_eligible(due_date: date, now_ist: datetime) -> bool:
    if now_ist.tzinfo is None:
        raise ValueError("now_ist must be timezone-aware")
    local = now_ist.astimezone(IST)
    if due_date < local.date():
        return True
    return due_date == local.date() and local.time().replace(tzinfo=None) >= POST_CLOSE_CAPTURE


def _provider_day(row: list) -> date:
    stamp = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Upstox daily candle timestamp must be timezone-aware")
    return stamp.astimezone(IST).date()


def exact_daily_candle(client: ReadOnlyClient, trading_date: date) -> dict:
    envelope = client.daily(trading_date, trading_date)
    validate_candles(envelope)
    rows = envelope["payload"]["data"].get("candles", [])
    matches = [row for row in rows if _provider_day(row) == trading_date]
    if len(matches) != 1:
        raise ValueError(f"exact NIFTY daily candle not available for {trading_date.isoformat()}")
    row = matches[0]
    return {
        "trading_date": trading_date,
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "source_ref": f"UPSTOX_AUTHENTICATED:NIFTY_DAILY:{trading_date.isoformat()}:{envelope['sha256']}",
        "provider_sha256": envelope["sha256"],
    }


def seed_missing_canonical_checkpoints(conn) -> int:
    """Seed canonical maturity checkpoints without inventing forecast values.

    Preferred dates come from immutable daily_forecasts. For legacy selected
    canonicals whose day-path rows were never persisted, seed eligibility-only
    D+1..D+5 dates from the verified 2026 trading calendar and target date. Those
    checkpoints may capture realized outcomes but remain unscored until original
    frozen forecast context exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO outcome_checkpoints
              (forecast_id, checkpoint_type, due_date, status, source_ref, notes)
            SELECT df.forecast_id,
                   'D+' || df.day_number::text,
                   df.trading_date,
                   'DUE',
                   'IMMUTABLE_DAILY_FORECAST_DATE',
                   'Seeded from existing immutable daily_forecasts row; no forecast value reconstructed.'
              FROM daily_forecasts df
              JOIN canonical_selections cs
                ON cs.selected_forecast_id=df.forecast_id
               AND cs.selection_status='SELECTED'
             WHERE df.trading_date IS NOT NULL
               AND NOT EXISTS (
                 SELECT 1
                   FROM outcome_checkpoints oc
                  WHERE oc.forecast_id=df.forecast_id
                    AND oc.checkpoint_type='D+' || df.day_number::text
               )
            """
        )
        count = max(cur.rowcount, 0)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cs.selected_forecast_id,cs.target_trading_date
              FROM canonical_selections cs
             WHERE cs.selection_status='SELECTED'
               AND cs.selected_forecast_id IS NOT NULL
             ORDER BY cs.target_trading_date
            """
        )
        selected = cur.fetchall()
    legacy_seeded = 0
    for forecast_id,target_date in selected:
        dates = [target_date] + next_trading_days_after(target_date, 4)
        for day_number,due_date in enumerate(dates, start=1):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO outcome_checkpoints
                      (forecast_id,checkpoint_type,due_date,status,source_ref,notes)
                    SELECT %s,%s,%s,'DUE','VERIFIED_2026_TRADING_CALENDAR',
                           'Eligibility checkpoint seeded from selected canonical target date; no forecast direction/range reconstructed.'
                    WHERE NOT EXISTS (
                      SELECT 1 FROM outcome_checkpoints
                       WHERE forecast_id=%s AND checkpoint_type=%s
                    )
                    """,
                    (forecast_id,f"D+{day_number}",due_date,forecast_id,f"D+{day_number}"),
                )
                legacy_seeded += max(cur.rowcount,0)
        conn.commit()
    return count + legacy_seeded


def _due_canonical_rows(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT oc.checkpoint_id,oc.forecast_id,oc.checkpoint_type,oc.due_date,oc.status
              FROM outcome_checkpoints oc
              JOIN canonical_selections cs
                ON cs.selected_forecast_id=oc.forecast_id
               AND cs.selection_status='SELECTED'
             WHERE oc.status='DUE'
               AND oc.checkpoint_type IN ('D+1','D+2','D+3','D+4','D+5')
             ORDER BY oc.due_date,oc.checkpoint_id
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _forecast_context(conn, forecast_id: str, day_number: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT df.trading_date,df.bias,df.probability,df.zone_low,df.zone_high,
                   f.spot_price
              FROM daily_forecasts df
              JOIN forecasts f ON f.forecast_id=df.forecast_id
             WHERE df.forecast_id=%s AND df.day_number=%s
             LIMIT 1
            """,
            (forecast_id, day_number),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        result = dict(zip(cols, row))
        if result["zone_low"] is None or result["zone_high"] is None or result["spot_price"] is None:
            return None
        return result


def _evaluation_exists(conn, forecast_id: str, day_number: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
              FROM v_latest_forecast_checkpoint_evaluation
             WHERE forecast_id=%s AND day_number=%s
             LIMIT 1
            """,
            (forecast_id, day_number),
        )
        return cur.fetchone() is not None


def _capture_checkpoint(conn, checkpoint: dict, candle: dict, context_missing: bool, now_utc: datetime) -> bool:
    notes = "Authenticated Upstox daily NIFTY OHLC captured after checkpoint maturity."
    if context_missing:
        notes += " Frozen daily forecast context is missing; outcome retained but not scored."
    observed = datetime.combine(checkpoint["due_date"], time(15, 30), tzinfo=IST)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE outcome_checkpoints
               SET status='CAPTURED',
                   observed_at=%s,
                   actual_nifty=%s,
                   period_high=%s,
                   period_low=%s,
                   source_ref=%s,
                   notes=%s
             WHERE checkpoint_id=%s AND status='DUE'
            """,
            (
                observed,
                candle["close"],
                candle["high"],
                candle["low"],
                candle["source_ref"],
                notes,
                checkpoint["checkpoint_id"],
            ),
        )
        changed = cur.rowcount == 1
    conn.commit()
    return changed


def _insert_evaluation(conn, checkpoint: dict, context: dict, candle: dict, evaluated_at: datetime) -> bool:
    day_number = PRIMARY[checkpoint["checkpoint_type"]]
    if _evaluation_exists(conn, checkpoint["forecast_id"], day_number):
        return False
    metrics = evaluate_forecast_checkpoint(
        bias=str(context["bias"]),
        reference_spot=float(context["spot_price"]),
        actual_close=float(candle["close"]),
        zone_low=float(context["zone_low"]),
        zone_high=float(context["zone_high"]),
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO forecast_checkpoint_evaluations
              (forecast_id,day_number,trading_date,evaluation_status,actual_close,
               reference_spot,bias,directional_hit,directional_margin_points,
               zone_hit,zone_error_points,probability,brier_score,source_ref,
               supersedes_evaluation_id,notes,evaluated_at)
            VALUES
              (%s,%s,%s,'SCORABLE',%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,NULL,%s,%s)
            """,
            (
                checkpoint["forecast_id"],
                day_number,
                context["trading_date"],
                candle["close"],
                context["spot_price"],
                context["bias"],
                metrics["directional_hit"],
                metrics["directional_margin_points"],
                metrics["zone_hit"],
                metrics["zone_error_points"],
                context["probability"],
                candle["source_ref"],
                "Automated canonical checkpoint evaluation from frozen daily forecast and authenticated Upstox close.",
                evaluated_at,
            ),
        )
    conn.commit()
    return True


def evaluate_captured_without_evaluation(conn, evaluated_at: datetime) -> tuple[int, int]:
    """Recover evaluations when a checkpoint was captured before the evaluator ran."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT oc.checkpoint_id,oc.forecast_id,oc.checkpoint_type,oc.due_date,
                   oc.actual_nifty,oc.period_high,oc.period_low,oc.source_ref
              FROM outcome_checkpoints oc
              JOIN canonical_selections cs
                ON cs.selected_forecast_id=oc.forecast_id
               AND cs.selection_status='SELECTED'
             WHERE oc.status='CAPTURED'
               AND oc.checkpoint_type IN ('D+1','D+2','D+3','D+4','D+5')
             ORDER BY oc.due_date,oc.checkpoint_id
            """
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    evaluated = missing = 0
    for checkpoint in rows:
        day_number = PRIMARY[checkpoint["checkpoint_type"]]
        if _evaluation_exists(conn, checkpoint["forecast_id"], day_number):
            continue
        context = _forecast_context(conn, checkpoint["forecast_id"], day_number)
        if context is None:
            missing += 1
            continue
        candle = {
            "close": float(checkpoint["actual_nifty"]),
            "high": float(checkpoint["period_high"]) if checkpoint["period_high"] is not None else float(checkpoint["actual_nifty"]),
            "low": float(checkpoint["period_low"]) if checkpoint["period_low"] is not None else float(checkpoint["actual_nifty"]),
            "source_ref": checkpoint["source_ref"] or "CAPTURED_CHECKPOINT",
        }
        if _insert_evaluation(conn, checkpoint, context, candle, evaluated_at):
            evaluated += 1
    return evaluated, missing


def reconcile_due_checkpoints(conn, token: str, now_ist: datetime | None = None) -> ReconciliationSummary:
    if not token or not token.strip():
        raise ValueError("UPSTOX_ANALYTICS_TOKEN is required")
    now_ist = now_ist or datetime.now(IST)
    if now_ist.tzinfo is None:
        raise ValueError("now_ist must be timezone-aware")
    now_utc = now_ist.astimezone(timezone.utc)
    seeded = seed_missing_canonical_checkpoints(conn)
    due = _due_canonical_rows(conn)
    client = ReadOnlyClient(token, opener=CurlOpener())
    cache: dict[date, dict] = {}
    eligible = captured = evaluated = already = missing = not_due = source_failures = 0

    for checkpoint in due:
        due_date = checkpoint["due_date"]
        if not checkpoint_is_capture_eligible(due_date, now_ist):
            not_due += 1
            continue
        eligible += 1
        day_number = PRIMARY[checkpoint["checkpoint_type"]]
        context = _forecast_context(conn, checkpoint["forecast_id"], day_number)
        try:
            candle = cache.get(due_date)
            if candle is None:
                candle = exact_daily_candle(client, due_date)
                cache[due_date] = candle
        except Exception:
            source_failures += 1
            continue
        if not _capture_checkpoint(conn, checkpoint, candle, context is None, now_utc):
            continue
        captured += 1
        if context is None:
            missing += 1
            continue
        if _evaluation_exists(conn, checkpoint["forecast_id"], day_number):
            already += 1
            continue
        if _insert_evaluation(conn, checkpoint, context, candle, now_utc):
            evaluated += 1

    recovered, recovered_missing = evaluate_captured_without_evaluation(conn, now_utc)
    evaluated += recovered
    missing += recovered_missing
    return ReconciliationSummary(
        seeded_checkpoints=seeded,
        due_seen=len(due),
        eligible_seen=eligible,
        captured=captured,
        evaluated=evaluated,
        already_evaluated=already,
        missing_frozen_forecast=missing,
        not_yet_due=not_due,
        source_failures=source_failures,
    )
