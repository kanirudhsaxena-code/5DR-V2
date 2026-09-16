"""Pure scheduling/watchdog policy for autonomous 5DR runs.

The scheduler deliberately contains no GitHub, database, broker, forecast or web calls.
A frequent external heartbeat may ask this module what is due.  Wide run windows plus
deterministic idempotency keys make the design resilient to delayed scheduler invocations
without allowing late evidence to masquerade as an on-time run.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError

IST = ZoneInfo("Asia/Kolkata")
CLASSIFICATIONS = {
    "CANONICAL_CANDIDATE",
    "INTRADAY_SNAPSHOT",
    "POST_CLOSE_RECONCILIATION",
}
DAY_ROLES = {"PREVIOUS_TRADING_DAY", "TARGET_TRADING_DAY"}


def _date(value, field):
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise DataArchitectureError(f"{field} invalid")
    return value


def _clock(value, field):
    if isinstance(value, time):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = time.fromisoformat(value)
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} invalid")
    if parsed.tzinfo is not None:
        raise DataArchitectureError(f"{field} must be local clock time")
    return parsed.replace(microsecond=0)


class NSESessionCalendar:
    """Small deterministic calendar boundary; official dates are injected upstream."""

    def __init__(self, *, closed_dates=(), special_open_dates=()):
        self.closed_dates = frozenset(_date(value, "closed date") for value in closed_dates)
        self.special_open_dates = frozenset(_date(value, "special open date") for value in special_open_dates)
        if self.closed_dates & self.special_open_dates:
            raise DataArchitectureError("calendar date cannot be both closed and open")

    def is_trading_day(self, value):
        value = _date(value, "trading date")
        if value in self.special_open_dates:
            return True
        return value.weekday() < 5 and value not in self.closed_dates

    def previous_trading_day(self, value):
        value = _date(value, "target trading date")
        probe = value - timedelta(days=1)
        for _ in range(14):
            if self.is_trading_day(probe):
                return probe
            probe -= timedelta(days=1)
        raise DataArchitectureError("previous trading day unresolved")

    def next_trading_day(self, value):
        value = _date(value, "trading date")
        probe = value + timedelta(days=1)
        for _ in range(14):
            if self.is_trading_day(probe):
                return probe
            probe += timedelta(days=1)
        raise DataArchitectureError("next trading day unresolved")


def validate_run_windows(windows):
    if not isinstance(windows, (list, tuple)) or not windows:
        raise DataArchitectureError("run windows missing")
    labels = set()
    normalized = []
    canonical_open = time(15, 20)
    target_open = time(9, 15)
    intraday_end = time(15, 20)
    for row in windows:
        if not isinstance(row, dict):
            raise DataArchitectureError("run window invalid")
        label = row.get("label")
        classification = row.get("classification")
        day_role = row.get("day_role")
        if not isinstance(label, str) or not label.strip() or len(label) > 64:
            raise DataArchitectureError("run window label invalid")
        label = label.strip().upper()
        if label in labels:
            raise DataArchitectureError("duplicate run window label")
        labels.add(label)
        if classification not in CLASSIFICATIONS:
            raise DataArchitectureError("run classification invalid")
        if day_role not in DAY_ROLES:
            raise DataArchitectureError("run day role invalid")
        start = _clock(row.get("start"), "run window start")
        end = _clock(row.get("end"), "run window end")
        if start >= end:
            raise DataArchitectureError("run window must not cross midnight")

        # Freeze the already-approved V2.1 canonical timing semantics.
        if classification == "CANONICAL_CANDIDATE":
            if day_role == "PREVIOUS_TRADING_DAY" and start < canonical_open:
                raise DataArchitectureError("previous-day canonical window starts before 15:20")
            if day_role == "TARGET_TRADING_DAY" and end > target_open:
                raise DataArchitectureError("target-day canonical window extends past 09:15")
        if classification == "INTRADAY_SNAPSHOT":
            if day_role != "TARGET_TRADING_DAY" or start < target_open or end > intraday_end:
                raise DataArchitectureError("intraday snapshot outside 09:15-15:20 target-day window")

        normalized.append({
            "label": label,
            "classification": classification,
            "day_role": day_role,
            "start": start.isoformat(),
            "end": end.isoformat(),
        })
    return normalized


def run_key(target_trading_date, label):
    target = _date(target_trading_date, "target trading date")
    if not isinstance(label, str) or not label.strip():
        raise DataArchitectureError("run key label invalid")
    return f"5DR:{target.isoformat()}:{label.strip().upper()}"


def _aware_ist(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DataArchitectureError("scheduler heartbeat timestamp must be timezone-aware")
    return value.astimezone(IST)


def assess_schedule(now, target_trading_date, windows, *, calendar,
                    completed_run_keys=()):
    if not isinstance(calendar, NSESessionCalendar):
        raise DataArchitectureError("NSE calendar boundary required")
    target = _date(target_trading_date, "target trading date")
    if not calendar.is_trading_day(target):
        raise DataArchitectureError("target date is not an NSE trading day")
    now_ist = _aware_ist(now)
    normalized = validate_run_windows(windows)
    completed = frozenset(completed_run_keys)
    if any(not isinstance(key, str) or not key for key in completed):
        raise DataArchitectureError("completed run key invalid")
    previous = calendar.previous_trading_day(target)
    assessments = []
    for row in normalized:
        run_date = previous if row["day_role"] == "PREVIOUS_TRADING_DAY" else target
        start = datetime.combine(run_date, time.fromisoformat(row["start"]), tzinfo=IST)
        end = datetime.combine(run_date, time.fromisoformat(row["end"]), tzinfo=IST)
        key = run_key(target, row["label"])
        if key in completed:
            status = "COMPLETED"
        elif now_ist < start:
            status = "UPCOMING"
        elif now_ist < end:
            status = "DUE"
        else:
            status = "MISSED"
        assessments.append({
            **row,
            "target_trading_date": target.isoformat(),
            "scheduled_run_date": run_date.isoformat(),
            "window_start": start.isoformat(),
            "window_end_exclusive": end.isoformat(),
            "run_key": key,
            "status": status,
            "execute_now": status == "DUE",
            "late_execution_permitted": False,
        })
    return assessments


def watchdog_summary(now, target_trading_date, windows, *, calendar,
                     completed_run_keys=()):
    rows = assess_schedule(
        now, target_trading_date, windows,
        calendar=calendar,
        completed_run_keys=completed_run_keys,
    )
    due = [row for row in rows if row["status"] == "DUE"]
    missed = [row for row in rows if row["status"] == "MISSED"]
    return {
        "schema": "5dr-autonomous-schedule-watchdog-v1",
        "heartbeat_at": _aware_ist(now).isoformat(),
        "target_trading_date": _date(target_trading_date, "target trading date").isoformat(),
        "due_run_keys": [row["run_key"] for row in due],
        "missed_run_keys": [row["run_key"] for row in missed],
        "due_count": len(due),
        "missed_count": len(missed),
        "all_windows": rows,
        "duplicate_suppression": "RUN_KEY",
        "late_execution_permitted": False,
    }
