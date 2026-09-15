"""5DR V2.2.2 autonomous recommendation lifecycle/checkpoint worker.

Pure decision logic only. It never fabricates missing market evidence and never
modifies forecasts or execution plans. Persistence remains append-only.
"""
from __future__ import annotations

ACTIONABLE = {"BUY_CE", "BUY_PE", "BUY_CONVEXITY"}
TERMINAL = {"T2_HIT", "SL_HIT", "THESIS_EXIT", "TIME_EXIT", "NOT_SCORABLE"}


def pct(entry: float, mark: float) -> float:
    return round(100.0 * (mark - entry) / entry, 4)


def r_multiple(entry: float, stop: float, mark: float) -> float | None:
    risk = entry - stop
    return None if risk <= 0 else round((mark - entry) / risk, 4)


def derive_events(*, entry: float, stop: float, target1: float, target2: float,
                  mark: float, existing_types: set[str]) -> list[dict]:
    """Return only objectively implied append-only events for a verified mark.

    A single snapshot can prove an upside target was reached when mark >= target,
    but it cannot prove ordering against an unobserved earlier stop. Therefore a
    caller must supply continuous/ordered evidence before using this helper to
    close a recommendation whose path ordering is ambiguous.
    """
    events: list[dict] = []
    if "T1_HIT" not in existing_types and mark >= target1:
        events.append({"event_type": "T1_HIT", "premium": target1,
                       "pnl_pct": pct(entry, target1),
                       "r_multiple": r_multiple(entry, stop, target1)})
    if "T2_HIT" not in existing_types and mark >= target2:
        events.append({"event_type": "T2_HIT", "premium": target2,
                       "pnl_pct": pct(entry, target2),
                       "r_multiple": r_multiple(entry, stop, target2)})
    if not ({"T1_HIT", "T2_HIT"} & existing_types) and mark <= stop:
        events.append({"event_type": "SL_HIT", "premium": stop,
                       "pnl_pct": pct(entry, stop),
                       "r_multiple": -1.0})
    return events


def checkpoint_due(due_date, as_of_date, status: str) -> bool:
    return status == "DUE" and due_date <= as_of_date


def should_process(recommendation: str, lifecycle_status: str) -> bool:
    return recommendation in ACTIONABLE and lifecycle_status not in {
        "CLOSED_T2", "CLOSED_SL", "CLOSED_THESIS_EXIT", "CLOSED_TIME_EXIT",
        "NOT_SCORABLE"
    }
