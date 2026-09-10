"""5DR V2.1.2 assessment and efficacy calculations.

Pure functions only. Persistence/reconciliation is handled separately.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean


def format_rate(numerator: int, denominator: int) -> str:
    """Return the mandatory numerator/denominator rate display."""
    if denominator <= 0:
        return "0/0 = N/A"
    return f"{numerator}/{denominator} = {100.0 * numerator / denominator:.1f}%"


def evaluate_forecast_checkpoint(
    *,
    bias: str,
    reference_spot: float,
    actual_close: float,
    zone_low: float,
    zone_high: float,
) -> dict:
    """Evaluate one D+n forecast checkpoint using frozen V2.1.2 rules."""
    bias = bias.upper()
    reference_spot = float(reference_spot)
    actual_close = float(actual_close)
    zone_low = float(zone_low)
    zone_high = float(zone_high)
    if zone_high < zone_low:
        raise ValueError("zone_high must be >= zone_low")

    zone_hit = zone_low <= actual_close <= zone_high
    if zone_hit:
        zone_error = 0.0
    else:
        zone_error = min(abs(actual_close - zone_low), abs(actual_close - zone_high))

    if bias == "BULLISH":
        margin = actual_close - reference_spot
        directional_hit = actual_close > reference_spot
    elif bias == "BEARISH":
        margin = reference_spot - actual_close
        directional_hit = actual_close < reference_spot
    elif bias == "RANGE":
        directional_hit = zone_hit
        if zone_hit:
            margin = min(actual_close - zone_low, zone_high - actual_close)
        else:
            margin = -zone_error
    else:
        raise ValueError("bias must be BULLISH, RANGE or BEARISH")

    return {
        "directional_hit": bool(directional_hit),
        "directional_margin_points": float(margin),
        "zone_hit": bool(zone_hit),
        "zone_error_points": float(zone_error),
    }


def aggregate_forecast_horizon(records: list[dict]) -> dict:
    """Aggregate one horizon's latest SCORABLE evaluation records."""
    scorable = [r for r in records if r.get("evaluation_status") == "SCORABLE"]
    hits = sum(bool(r.get("directional_hit")) for r in scorable)
    zone_hits = sum(bool(r.get("zone_hit")) for r in scorable)
    return {
        "scorable_count": len(scorable),
        "directional_hits": hits,
        "directional_accuracy": format_rate(hits, len(scorable)),
        "zone_hits": zone_hits,
        "zone_hit_rate": format_rate(zone_hits, len(scorable)),
        "average_directional_margin_points": (
            mean(float(r["directional_margin_points"]) for r in scorable)
            if scorable
            else None
        ),
        "average_zone_error_points": (
            mean(float(r["zone_error_points"]) for r in scorable)
            if scorable
            else None
        ),
    }


def aggregate_all_horizons(records: list[dict]) -> dict:
    """Return mandatory D+1 through D+5 slots, even with zero samples."""
    grouped: dict[int, list[dict]] = defaultdict(list)
    for record in records:
        grouped[int(record["day_number"])].append(record)
    return {f"D+{day}": aggregate_forecast_horizon(grouped[day]) for day in range(1, 6)}


def aggregate_recommendations(records: list[dict]) -> dict:
    """Aggregate current recommendation ledger records.

    Expected record keys include status, primary_outcome, final_pnl_pct,
    current_pnl_pct and r_multiple. Missing optional values are ignored.
    """
    total = len(records)
    actionable = [r for r in records if r.get("recommendation") != "NO_TRADE"]
    wins = [r for r in actionable if r.get("primary_outcome") == "WIN"]
    losses = [r for r in actionable if r.get("primary_outcome") == "LOSS"]
    resolved = wins + losses
    open_rows = [r for r in actionable if r.get("status") == "OPEN"]
    untriggered = [r for r in actionable if r.get("status") == "UNTRIGGERED"]
    not_scorable = [r for r in actionable if r.get("status") == "NOT_SCORABLE"]

    realized_pnls = [float(r["final_pnl_pct"]) for r in resolved if r.get("final_pnl_pct") is not None]
    open_pnls = [float(r["current_pnl_pct"]) for r in open_rows if r.get("current_pnl_pct") is not None]
    rs = [float(r["r_multiple"]) for r in resolved if r.get("r_multiple") is not None]

    return {
        "total_recommendations": total,
        "actionable_calls": len(actionable),
        "resolved": len(resolved),
        "wins": len(wins),
        "losses": len(losses),
        "open": len(open_rows),
        "untriggered": len(untriggered),
        "not_scorable": len(not_scorable),
        "hit_rate": format_rate(len(wins), len(resolved)),
        "average_r": mean(rs) if rs else None,
        "realized_standardized_model_pnl_pct": sum(realized_pnls) if realized_pnls else 0.0,
        "open_standardized_mtm_pct": sum(open_pnls) if open_pnls else 0.0,
    }
