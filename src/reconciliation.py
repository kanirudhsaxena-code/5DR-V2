"""5DR V2.1.2 recommendation event reconciliation helpers."""

from __future__ import annotations

TERMINAL_PRIMARY = {"T1_HIT", "SL_HIT", "TIME_EXIT", "NOT_SCORABLE"}


def recommendation_primary_state(events: list[dict]) -> dict:
    """Derive primary recommendation state from an append-only event stream.

    Events are processed in timestamp order. T1-before-SL is a WIN; SL-before-T1
    is a LOSS. T2 is secondary and never changes the primary result.
    """
    if not events:
        return {"status": "UNTRIGGERED", "primary_outcome": None}

    ordered = sorted(events, key=lambda e: (e.get("event_timestamp"), e.get("event_id", 0)))
    entered = False
    status = "UNTRIGGERED"
    outcome = None

    for event in ordered:
        et = event["event_type"]
        if et == "NOT_SCORABLE":
            return {"status": "NOT_SCORABLE", "primary_outcome": None}
        if et == "ENTRY_TRIGGERED":
            entered = True
            status = "OPEN"
            continue
        if not entered:
            continue
        if et == "T1_HIT":
            return {"status": "T1_HIT", "primary_outcome": "WIN"}
        if et == "SL_HIT":
            return {"status": "SL_HIT", "primary_outcome": "LOSS"}
        if et == "TIME_EXIT":
            pnl = event.get("pnl_pct")
            if pnl is None:
                return {"status": "TIME_EXIT", "primary_outcome": None}
            return {"status": "TIME_EXIT", "primary_outcome": "WIN" if float(pnl) > 0 else "LOSS"}

    return {"status": status, "primary_outcome": outcome}
