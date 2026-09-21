"""Bridge complete published EDGE Console 5DR runs into canonical 5DR persistence.

This module imports only immutable Console runs that already contain a complete
D+1..D+5 forecast path. Earlier hollow/partial Console runs are intentionally
ignored. Canonical selection is finalized only after the existing V2.1 window
closes; importing a candidate never selects it early.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
NY = ZoneInfo("America/New_York")
CANONICAL_TIMING_ACTIVATION_TARGET_DATE = date(2026, 9, 22)
PREOPEN_WINDOW_START = time(8, 40)
PREOPEN_REQUEST_CUTOFF = time(8, 55)
HARD_CANONICAL_COMPLETION_CUTOFF = time(9, 0)
NYSE_HOLIDAYS_2026 = {
    date(2026,1,1), date(2026,1,19), date(2026,2,16), date(2026,4,3),
    date(2026,5,25), date(2026,6,19), date(2026,7,3), date(2026,9,7),
    date(2026,11,26), date(2026,12,25),
}
NYSE_EARLY_CLOSES_2026 = {date(2026,11,27), date(2026,12,24)}
HORIZONS = tuple(f"D+{i}" for i in range(1, 6))
DIRECTIONS = {"BULLISH", "RANGE", "BEARISH"}

# NSE equity trading holidays for calendar 2026, sourced from the official
# exchange holiday calendar. Weekend handling is separate.
NSE_HOLIDAYS_2026 = {
    date(2026,1,15), date(2026,1,26), date(2026,2,19), date(2026,3,3),
    date(2026,3,19), date(2026,3,26), date(2026,3,31), date(2026,4,1),
    date(2026,4,3), date(2026,4,14), date(2026,5,1), date(2026,5,28),
    date(2026,6,26), date(2026,8,26), date(2026,9,14), date(2026,10,2),
    date(2026,10,20), date(2026,11,10), date(2026,11,24), date(2026,12,25),
}

REGIME_WEIGHTS = {
    "TREND": {"PRICE_STRUCTURE": 40.0, "PVPO": 30.0, "PARTICIPATION": 15.0, "MACRO_CATALYSTS": 15.0},
    "RANGE": {"PRICE_STRUCTURE": 30.0, "PVPO": 35.0, "PARTICIPATION": 15.0, "MACRO_CATALYSTS": 20.0},
    "TRANSITION": {"PRICE_STRUCTURE": 35.0, "PVPO": 25.0, "PARTICIPATION": 15.0, "MACRO_CATALYSTS": 25.0},
    "EVENT_SHOCK": {"PRICE_STRUCTURE": 30.0, "PVPO": 20.0, "PARTICIPATION": 10.0, "MACRO_CATALYSTS": 40.0},
}


@dataclass(frozen=True)
class SyncSummary:
    console_runs_seen: int
    complete_runs_seen: int
    imported: int
    already_imported: int
    skipped_incomplete: int
    selections_finalized: int

    def to_dict(self) -> dict:
        return asdict(self)


def is_trading_day(day: date) -> bool:
    if day.year != 2026:
        raise ValueError("trading calendar is only verified for 2026")
    return day.weekday() < 5 and day not in NSE_HOLIDAYS_2026


def next_trading_day(day: date) -> date:
    cursor = day
    for _ in range(370):
        cursor += timedelta(days=1)
        if is_trading_day(cursor):
            return cursor
    raise ValueError("next trading day not found")


def previous_trading_day(day: date) -> date:
    cursor = day
    for _ in range(370):
        cursor -= timedelta(days=1)
        if is_trading_day(cursor):
            return cursor
    raise ValueError("previous trading day not found")


def next_trading_days_after(day: date, count: int = 5) -> list[date]:
    out: list[date] = []
    cursor = day
    while len(out) < count:
        cursor = next_trading_day(cursor)
        out.append(cursor)
    return out


def _is_nyse_session(day: date) -> bool:
    return day.weekday() < 5 and day not in NYSE_HOLIDAYS_2026


def last_nyse_core_close_before(target_open_ist: datetime) -> datetime:
    """Return the latest completed NYSE cash-session close before target NSE open.

    Uses the official 2026 holiday calendar, America/New_York DST rules, and known
    2026 early-close dates. This is the lower bound for an overnight fallback.
    """
    if target_open_ist.tzinfo is None:
        raise ValueError("target_open_ist must be timezone-aware")
    candidate = target_open_ist.astimezone(NY).date()
    for _ in range(10):
        if _is_nyse_session(candidate):
            close_time = time(13, 0) if candidate in NYSE_EARLY_CLOSES_2026 else time(16, 0)
            close_ny = datetime.combine(candidate, close_time, tzinfo=NY)
            if close_ny < target_open_ist.astimezone(NY):
                return close_ny.astimezone(IST)
        candidate -= timedelta(days=1)
    raise ValueError("NYSE close could not be resolved")


def _requested_at(request_metadata: dict | None, completed_at: datetime) -> datetime:
    if isinstance(request_metadata, dict):
        invocation = request_metadata.get("invocation")
        if isinstance(invocation, dict):
            raw = invocation.get("requested_at")
            if isinstance(raw, str) and raw.strip():
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    return parsed
    return completed_at


def classify_run(run_timestamp: datetime, request_metadata: dict | None = None) -> dict:
    if run_timestamp.tzinfo is None:
        raise ValueError("run timestamp must be timezone-aware")
    completed_local = run_timestamp.astimezone(IST)
    requested_local = _requested_at(request_metadata, run_timestamp).astimezone(IST)
    day = requested_local.date()
    clock = requested_local.time().replace(tzinfo=None)

    if is_trading_day(day) and clock < time(15, 30):
        target = day
    else:
        target = next_trading_day(day)

    target_open = datetime.combine(target, time(9, 0), tzinfo=IST)
    hard_close = target_open
    prior = previous_trading_day(target)

    # Legacy history keeps the previous production rule and is never rewritten.
    if target < CANONICAL_TIMING_ACTIVATION_TARGET_DATE:
        window_open = datetime.combine(prior, time(0, 0), tzinfo=IST)
        window_close = target_open
        candidate = window_open <= requested_local < window_close and completed_local < hard_close
        canonical_type = "LEGACY_CANONICAL" if candidate else "DIAGNOSTIC_SNAPSHOT"
        run_class = "CANONICAL_CANDIDATE" if candidate else "INTRADAY_SNAPSHOT"
        evidence_mode = "MARKET_CLOSED_CARRY_FORWARD" if candidate else "MIXED"
    else:
        preopen_open = datetime.combine(target, PREOPEN_WINDOW_START, tzinfo=IST)
        request_cutoff = datetime.combine(target, PREOPEN_REQUEST_CUTOFF, tzinfo=IST)
        overnight_open = last_nyse_core_close_before(target_open)
        if preopen_open <= requested_local <= request_cutoff and completed_local < hard_close:
            canonical_type = "PREOPEN_CANONICAL"
            run_class = "CANONICAL_CANDIDATE"
            evidence_mode = "PREOPEN_REFRESH"
            window_open = preopen_open
            window_close = hard_close
        elif overnight_open <= requested_local < preopen_open and completed_local < hard_close:
            canonical_type = "OVERNIGHT_FALLBACK_CANONICAL"
            run_class = "CANONICAL_CANDIDATE"
            evidence_mode = "MIXED"
            window_open = overnight_open
            window_close = hard_close
        else:
            canonical_type = "DIAGNOSTIC_SNAPSHOT"
            run_class = "INTRADAY_SNAPSHOT"
            evidence_mode = "MIXED"
            window_open = datetime.combine(prior, time(15, 30), tzinfo=IST)
            window_close = hard_close

    daily_dates = [target] + next_trading_days_after(target, 4)
    return {
        "target_trading_date": target,
        "run_class": run_class,
        "canonical_type": canonical_type,
        "evidence_mode": evidence_mode,
        "window_open": window_open,
        "window_close": window_close,
        "requested_at": requested_local,
        "completed_at": completed_local,
        "daily_dates": daily_dates,
    }


def _num(value) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def complete_horizon_slots(result: dict) -> dict | None:
    slots = result.get("horizon_slots")
    if not isinstance(slots, dict):
        return None
    clean: dict[str, dict] = {}
    for horizon in HORIZONS:
        slot = slots.get(horizon)
        if not isinstance(slot, dict):
            return None
        direction = str(slot.get("direction") or "")
        probability = _num(slot.get("probability"))
        low = _num(slot.get("zone_low"))
        high = _num(slot.get("zone_high"))
        if direction not in DIRECTIONS or probability is None or not 0 <= probability <= 100:
            return None
        if low is None or high is None or low <= 0 or high < low:
            return None
        clean[horizon] = {
            "direction": direction,
            "probability": probability,
            "zone_low": low,
            "zone_high": high,
            "basis": str(slot.get("basis") or "").strip() or None,
        }
    return clean


def _spot_from_metadata(metadata: dict) -> float | None:
    evidence = metadata.get("automated_market_evidence")
    if not isinstance(evidence, dict):
        return None
    for observation in evidence.get("observations") or []:
        if not isinstance(observation, dict) or observation.get("category") != "PRICE_TECHNICALS":
            continue
        data = observation.get("structured_data")
        if not isinstance(data, dict):
            continue
        nifty = data.get("nifty")
        if not isinstance(nifty, dict):
            continue
        spot = nifty.get("spot")
        if isinstance(spot, dict):
            value = _num(spot.get("last_price"))
            if value is not None and value > 0:
                return value
    return None


def _normalized_from_metadata(metadata: dict) -> dict | None:
    handoff = metadata.get("intelligence_handoff")
    if not isinstance(handoff, dict):
        return None
    normalized = handoff.get("normalized")
    return normalized if isinstance(normalized, dict) else None


def _headline_direction(label: str) -> str:
    upper = str(label or "").upper()
    if "BULL" in upper:
        return "BULLISH"
    if "BEAR" in upper:
        return "BEARISH"
    return "RANGE"


def _marker(console_run_id: str) -> str:
    return f"EDGE_CONSOLE_RUN_ID={console_run_id}"


def _existing_import(conn, console_run_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.forecast_id
              FROM runs r
              JOIN forecasts f ON f.run_id=r.run_id
             WHERE r.notes=%s
             LIMIT 1
            """,
            (_marker(console_run_id),),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _forecast_id(console_run_id: str, run_timestamp: datetime) -> str:
    suffix = console_run_id.replace("5drrun_", "").replace("-", "")[:10]
    local = run_timestamp.astimezone(IST)
    return f"5DR-CNS-{local:%Y%m%d-%H%M}-{suffix}"


def _session_label(ts: datetime) -> str:
    local = ts.astimezone(IST)
    if not is_trading_day(local.date()):
        return "NON_TRADING"
    clock = local.time().replace(tzinfo=None)
    if clock < time(9, 15):
        return "PREOPEN"
    if clock < time(15, 30):
        return "INTRADAY"
    return "POST_CLOSE"


def import_console_run(conn, run: dict, request: dict) -> str | None:
    console_run_id = str(run.get("run_id") or "").strip()
    if not console_run_id:
        return None
    existing = _existing_import(conn, console_run_id)
    if existing:
        return existing

    result = run.get("result")
    if not isinstance(result, dict):
        return None
    slots = complete_horizon_slots(result)
    if slots is None:
        return None
    if result.get("model_version") != "5DR_V2_1" or result.get("output_contract_version") != "5DR_V2_1_2":
        return None
    timestamp = datetime.fromisoformat(str(run.get("generated_at") or "").replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        return None

    metadata = request.get("metadata") if isinstance(request, dict) else None
    if not isinstance(metadata, dict):
        return None
    normalized = _normalized_from_metadata(metadata)
    if not isinstance(normalized, dict):
        return None
    regime = str(normalized.get("regime") or "")
    event_shock = str(normalized.get("event_shock") or "")
    if regime not in REGIME_WEIGHTS or event_shock not in {"LOW","MODERATE","HIGH","EXTREME"}:
        return None
    spot = _spot_from_metadata(metadata)
    if spot is None:
        return None

    classification = classify_run(timestamp, metadata)
    forecast_id = _forecast_id(console_run_id, timestamp)
    probs = result.get("probabilities") or {}
    bull = _num(probs.get("BULL"))
    range_prob = _num(probs.get("RANGE"))
    bear = _num(probs.get("BEAR"))
    des5 = _num(result.get("des5"))
    trust = _num(result.get("market_trust"))
    edge = _num(result.get("execution_edge"))
    if None in (bull, range_prob, bear, des5, trust, edge):
        return None
    definitive = _headline_direction(str(result.get("directional_label") or ""))
    tradeable = result.get("tradeable") is True
    recommendation = "NO_TRADE"
    if tradeable:
        recommendation = "BUY_CE" if definitive == "BULLISH" else ("BUY_PE" if definitive == "BEARISH" else "BUY_CONVEXITY")
    blockers = result.get("tradeability_blockers")
    blocker_text = ", ".join(map(str, blockers)) if isinstance(blockers, list) and blockers else None
    zone_low = min(slot["zone_low"] for slot in slots.values())
    zone_high = max(slot["zone_high"] for slot in slots.values())
    raw_hash = hashlib.sha256(json.dumps(run, sort_keys=True, separators=(",",":"), default=str).encode()).hexdigest()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fg.forecast_id
              FROM forecast_governance fg
              JOIN forecasts f ON f.forecast_id=fg.forecast_id
             WHERE fg.target_trading_date=%s
             ORDER BY f.run_timestamp DESC
             LIMIT 1
            """,
            (classification["target_trading_date"],),
        )
        predecessor_row = cur.fetchone()
        predecessor = predecessor_row[0] if predecessor_row else None
        cur.execute(
            "SELECT COUNT(*) FROM forecast_governance WHERE target_trading_date=%s",
            (classification["target_trading_date"],),
        )
        sequence = int(cur.fetchone()[0]) + 1

        cur.execute(
            """
            INSERT INTO runs(command_type,run_timestamp,market_session,model_version,status,parent_run_id,notes)
            VALUES ('5DR',%s,%s,'5DR_V2_1','COMMITTED',NULL,%s)
            RETURNING run_id
            """,
            (timestamp, _session_label(timestamp), _marker(console_run_id)),
        )
        db_run_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO forecasts(
              forecast_id,parent_forecast_id,run_id,model_version,run_timestamp,spot_price,
              forecast_horizon,regime,des5,definitive_forecast,bull_probability,range_probability,
              bear_probability,expected_zone_low,expected_zone_high,market_trust_score,
              market_trust_band,event_shock_level,event_transmission,convexity_warranted,
              directional_trade,recommendation,tradeability_failure_reason,committed_at,record_hash,
              forecast_assessment,recommendation_assessment,output_contract_version
            ) VALUES (
              %s,%s,%s,'5DR_V2_1',%s,%s,'5D',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'UNKNOWN',
              false,%s,%s,%s,now(),%s,%s,%s,'5DR_V2_1_2'
            )
            """,
            (
                forecast_id, predecessor, db_run_id, timestamp, spot, regime, des5, definitive,
                bull, range_prob, bear, zone_low, zone_high, trust, result.get("market_trust_band"),
                event_shock, tradeable, recommendation, blocker_text, raw_hash,
                "Imported from a governed published EDGE Console 5DR run with complete D+1..D+5 path.",
                "Tradeability gate passed." if tradeable else (blocker_text or "NO_TRADE"),
            ),
        )

        for index, horizon in enumerate(HORIZONS, start=1):
            slot = slots[horizon]
            cur.execute(
                """
                INSERT INTO daily_forecasts(
                  forecast_id,day_number,trading_date,bias,probability,zone_low,zone_high,key_event_risk,notes
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    forecast_id, index, classification["daily_dates"][index-1], slot["direction"],
                    slot["probability"], slot["zone_low"], slot["zone_high"], event_shock, slot["basis"],
                ),
            )

        for component, score in (normalized.get("component_scores") or {}).items():
            if component not in REGIME_WEIGHTS[regime] or _num(score) is None:
                continue
            cur.execute(
                """
                INSERT INTO component_scores(
                  forecast_id,component,regime_weight,component_score,raw_detail,evidence_quality,notes
                ) VALUES (%s,%s,%s,%s,'{}'::jsonb,'HIGH',%s)
                """,
                (
                    forecast_id, component, REGIME_WEIGHTS[regime][component], float(score),
                    "Imported from EDGE Console governed intelligence handoff.",
                ),
            )

        execution = normalized.get("execution_inputs") if isinstance(normalized.get("execution_inputs"), dict) else {}
        cur.execute(
            """
            INSERT INTO execution_plans(
              forecast_id,execution_edge,rr_score,premium_iv_theta_score,strike_expiry_fit_score,
              liquidity_spread_score,entry_invalidation_score,instrument,expected_rr,option_suitability,notes
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                forecast_id, edge,
                _num(execution.get("rr_score")) or 0,
                _num(execution.get("premium_iv_theta_score")) or 0,
                _num(execution.get("strike_expiry_fit_score")) or 0,
                _num(execution.get("liquidity_spread_score")) or 0,
                _num(execution.get("entry_invalidation_score")) or 0,
                "NONE" if not tradeable else ("CE" if recommendation=="BUY_CE" else ("PE" if recommendation=="BUY_PE" else "CONVEXITY")),
                _num(normalized.get("expected_rr")) or 0,
                "REJECT" if not tradeable else "TRADEABLE",
                "Imported from complete EDGE Console 5DR run.",
            ),
        )

        cur.execute(
            """
            INSERT INTO forecast_governance(
              forecast_id,target_trading_date,run_class,validity_status,validity_reason,evidence_mode,
              predecessor_forecast_id,sequence_in_lineage,canonical_window_open,canonical_window_close
            ) VALUES (%s,%s,%s,'VALID',%s,%s,%s,%s,%s,%s)
            """,
            (
                forecast_id, classification["target_trading_date"], classification["run_class"],
                f"canonical_type={classification['canonical_type']}; requested_at={classification['requested_at'].isoformat()}; completed_at={classification['completed_at'].isoformat()}; complete immutable D+1..D+5 path.",
                classification["evidence_mode"], predecessor, sequence, classification["window_open"], classification["window_close"],
            ),
        )
    conn.commit()
    return forecast_id


def _candidate_type(validity_reason: str | None, evidence_mode: str) -> str:
    text = str(validity_reason or "")
    for value in ("PREOPEN_CANONICAL","OVERNIGHT_FALLBACK_CANONICAL","LEGACY_CANONICAL"):
        if f"canonical_type={value}" in text:
            return value
    if evidence_mode == "PREOPEN_REFRESH":
        return "PREOPEN_CANONICAL"
    if evidence_mode == "MARKET_CLOSED_CARRY_FORWARD":
        return "LEGACY_CANONICAL"
    return "OVERNIGHT_FALLBACK_CANONICAL"


def finalize_closed_canonical_windows(conn, now_ist: datetime | None = None) -> int:
    """Finalize one official canonical per target trading date.

    Post-activation preference is PREOPEN_CANONICAL, then overnight fallback,
    otherwise CANONICAL_MISSED. Legacy targets preserve the historical latest-valid
    rule. Selection is append-only because canonical_selections is immutable.
    """
    now_ist = now_ist or datetime.now(IST)
    if now_ist.tzinfo is None:
        raise ValueError("now_ist must be timezone-aware")
    local_now = now_ist.astimezone(IST)
    hard_boundary = datetime.combine(local_now.date(), HARD_CANONICAL_COMPLETION_CUTOFF, tzinfo=IST)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT target_trading_date
              FROM forecast_governance fg
             WHERE fg.run_class='CANONICAL_CANDIDATE'
               AND fg.validity_status='VALID'
               AND fg.canonical_window_close <= %s
               AND NOT EXISTS (
                 SELECT 1 FROM canonical_selections cs
                  WHERE cs.target_trading_date=fg.target_trading_date
               )
             ORDER BY target_trading_date
            """,
            (local_now,),
        )
        targets = [row[0] for row in cur.fetchall()]

    # A post-activation trading day with no eligible candidates must still become
    # explicitly CANONICAL_MISSED after the 09:00 hard boundary.
    today = local_now.date()
    if (
        today >= CANONICAL_TIMING_ACTIVATION_TARGET_DATE
        and is_trading_day(today)
        and local_now >= hard_boundary
    ):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM canonical_selections WHERE target_trading_date=%s LIMIT 1",
                (today,),
            )
            if cur.fetchone() is None and today not in targets:
                targets.append(today)

    finalized = 0
    for target in sorted(targets):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT fg.forecast_id,fg.canonical_window_open,fg.canonical_window_close,
                       f.run_timestamp,fg.validity_reason,fg.evidence_mode
                  FROM forecast_governance fg
                  JOIN forecasts f ON f.forecast_id=fg.forecast_id
                 WHERE fg.target_trading_date=%s
                   AND fg.run_class='CANONICAL_CANDIDATE'
                   AND fg.validity_status='VALID'
                   AND f.run_timestamp < fg.canonical_window_close
                   AND EXISTS (
                     SELECT 1
                       FROM daily_forecasts df
                      WHERE df.forecast_id=fg.forecast_id
                      GROUP BY df.forecast_id
                     HAVING COUNT(*)=5
                        AND COUNT(DISTINCT df.day_number)=5
                        AND MIN(df.day_number)=1
                        AND MAX(df.day_number)=5
                        AND COUNT(*) FILTER (
                          WHERE df.bias IS NULL OR df.probability IS NULL
                             OR df.zone_low IS NULL OR df.zone_high IS NULL
                        )=0
                   )
                """,
                (target,),
            )
            rows = cur.fetchall()

            candidates = []
            for row in rows:
                forecast_id,window_open,window_close,run_ts,reason,evidence_mode = row
                ctype = _candidate_type(reason,evidence_mode)
                candidates.append((forecast_id,window_open,window_close,run_ts,ctype))

            if target < CANONICAL_TIMING_ACTIVATION_TARGET_DATE:
                candidates.sort(key=lambda row: row[3], reverse=True)
            else:
                priority={"PREOPEN_CANONICAL":3,"OVERNIGHT_FALLBACK_CANONICAL":2,"LEGACY_CANONICAL":1}
                candidates.sort(key=lambda row:(priority.get(row[4],0),row[3]),reverse=True)

            if candidates:
                selected_id,window_open,window_close,_,canonical_type = candidates[0]
                first_id = sorted(candidates,key=lambda row:row[3])[0][0]
                cur.execute(
                    """
                    INSERT INTO canonical_selections(
                      target_trading_date,selection_status,selected_forecast_id,first_candidate_forecast_id,
                      selected_at,window_open_at,window_close_at,selection_rule,selection_reason
                    ) VALUES (%s,'SELECTED',%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (target_trading_date) DO NOTHING
                    """,
                    (
                        target,selected_id,first_id,local_now,window_open,window_close,
                        canonical_type,
                        f"{canonical_type}: latest valid complete candidate selected under frozen timing governance.",
                    ),
                )
                finalized += max(cur.rowcount,0)
            elif target >= CANONICAL_TIMING_ACTIVATION_TARGET_DATE:
                window_open = datetime.combine(target, PREOPEN_WINDOW_START, tzinfo=IST)
                window_close = datetime.combine(target, HARD_CANONICAL_COMPLETION_CUTOFF, tzinfo=IST)
                if local_now >= window_close:
                    cur.execute(
                        """
                        INSERT INTO canonical_selections(
                          target_trading_date,selection_status,selected_forecast_id,first_candidate_forecast_id,
                          selected_at,window_open_at,window_close_at,selection_rule,selection_reason
                        ) VALUES (%s,'NO_VALID_CANDIDATE',NULL,NULL,%s,%s,%s,'CANONICAL_MISSED',%s)
                        ON CONFLICT (target_trading_date) DO NOTHING
                        """,
                        (
                            target,local_now,window_open,window_close,
                            "No complete PREOPEN_CANONICAL or qualifying OVERNIGHT_FALLBACK_CANONICAL existed by the hard 09:00 IST boundary.",
                        ),
                    )
                    finalized += max(cur.rowcount,0)
        conn.commit()
    return finalized

def sync_console_runs(conn, runs: list[dict], request_fetcher, now_ist: datetime | None = None) -> SyncSummary:
    imported = existing = incomplete = complete = 0
    for run in sorted(runs, key=lambda row: str(row.get("generated_at") or "")):
        result = run.get("result")
        if not isinstance(result, dict) or complete_horizon_slots(result) is None:
            incomplete += 1
            continue
        complete += 1
        console_run_id = str(run.get("run_id") or "")
        if _existing_import(conn, console_run_id):
            existing += 1
            continue
        request = request_fetcher(console_run_id)
        forecast_id = import_console_run(conn, run, request)
        if forecast_id:
            imported += 1
        else:
            incomplete += 1
    finalized = finalize_closed_canonical_windows(conn, now_ist=now_ist)
    return SyncSummary(
        console_runs_seen=len(runs),
        complete_runs_seen=complete,
        imported=imported,
        already_imported=existing,
        skipped_incomplete=incomplete,
        selections_finalized=finalized,
    )
