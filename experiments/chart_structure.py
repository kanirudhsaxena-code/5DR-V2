"""Deterministic chart-structure evidence derived from validated OHLC candles.

This module replaces visual chart reading at the acquisition/evidence layer only.  It
never assigns a PVS raw score, DES5 value, regime weight, probability, or trade decision.
Those frozen 5DR semantics remain downstream.
"""
from datetime import datetime, timezone
from statistics import median

from experiments.data_contract import DataArchitectureError
from experiments.upstox_quality import validate_ohlc

SUPPORTED_TIMEFRAMES = frozenset({"1d", "1h", "30m", "15m", "5m"})


def _validated_rows(rows, *, minimum=3):
    if not isinstance(rows, list) or len(rows) < minimum:
        raise DataArchitectureError("chart candle history insufficient")
    normalized = []
    seen = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 7:
            raise DataArchitectureError("chart candle schema invalid")
        try:
            stamp = datetime.fromisoformat(row[0])
        except (TypeError, ValueError):
            raise DataArchitectureError("chart candle timestamp invalid") from None
        if stamp.tzinfo is None:
            raise DataArchitectureError("chart candle timestamp naive")
        stamp = stamp.astimezone(timezone.utc)
        if stamp in seen:
            raise DataArchitectureError("chart candle timestamp duplicated")
        seen.add(stamp)
        validate_ohlc(row[1], row[2], row[3], row[4], volume=row[5], open_interest=row[6])
        normalized.append([stamp.isoformat(), row[1], row[2], row[3], row[4], row[5], row[6]])
    normalized.sort(key=lambda row: row[0])
    return normalized


def swing_points(rows, *, radius=2):
    rows = _validated_rows(rows, minimum=2 * radius + 3)
    if isinstance(radius, bool) or not isinstance(radius, int) or radius < 1 or radius > 10:
        raise DataArchitectureError("swing radius invalid")
    highs, lows = [], []
    for index in range(radius, len(rows) - radius):
        current_high = rows[index][2]
        current_low = rows[index][3]
        neighbour_highs = [rows[j][2] for j in range(index - radius, index + radius + 1) if j != index]
        neighbour_lows = [rows[j][3] for j in range(index - radius, index + radius + 1) if j != index]
        if current_high > max(neighbour_highs):
            highs.append({"timestamp": rows[index][0], "price": current_high, "index": index})
        if current_low < min(neighbour_lows):
            lows.append({"timestamp": rows[index][0], "price": current_low, "index": index})
    return {"swing_highs": highs, "swing_lows": lows}


def _trend_from_swings(swings):
    highs = swings["swing_highs"]
    lows = swings["swing_lows"]
    if len(highs) < 2 or len(lows) < 2:
        return {
            "state": "INSUFFICIENT_SWINGS",
            "high_sequence": "UNKNOWN",
            "low_sequence": "UNKNOWN",
        }
    high_sequence = "HH" if highs[-1]["price"] > highs[-2]["price"] else "LH" if highs[-1]["price"] < highs[-2]["price"] else "EH"
    low_sequence = "HL" if lows[-1]["price"] > lows[-2]["price"] else "LL" if lows[-1]["price"] < lows[-2]["price"] else "EL"
    if high_sequence == "HH" and low_sequence == "HL":
        state = "UPTREND_STRUCTURE"
    elif high_sequence == "LH" and low_sequence == "LL":
        state = "DOWNTREND_STRUCTURE"
    else:
        state = "MIXED_OR_TRANSITION_STRUCTURE"
    return {"state": state, "high_sequence": high_sequence, "low_sequence": low_sequence}


def _recent_gaps(rows, *, min_gap_pct=0.0, limit=5):
    if isinstance(min_gap_pct, bool) or not isinstance(min_gap_pct, (int, float)) or min_gap_pct < 0:
        raise DataArchitectureError("gap threshold invalid")
    gaps = []
    for previous, current in zip(rows[:-1], rows[1:]):
        previous_close = float(previous[4])
        if previous_close <= 0:
            raise DataArchitectureError("gap reference close invalid")
        if current[3] > previous[2]:
            gap_points = current[3] - previous[2]
            direction = "GAP_UP"
        elif current[2] < previous[3]:
            gap_points = previous[3] - current[2]
            direction = "GAP_DOWN"
        else:
            continue
        gap_pct = 100.0 * gap_points / previous_close
        if gap_pct + 1e-12 < min_gap_pct:
            continue
        gaps.append({
            "timestamp": current[0],
            "direction": direction,
            "gap_points": round(gap_points, 6),
            "gap_pct": round(gap_pct, 6),
        })
    return gaps[-limit:]


def _range_event(rows, *, lookback):
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 3:
        raise DataArchitectureError("breakout lookback invalid")
    if len(rows) < lookback + 1:
        lookback = len(rows) - 1
    prior = rows[-(lookback + 1):-1]
    current = rows[-1]
    prior_high = max(row[2] for row in prior)
    prior_low = min(row[3] for row in prior)
    close = current[4]
    high = current[2]
    low = current[3]

    if close > prior_high:
        close_state = "CLOSE_ABOVE_PRIOR_RANGE"
    elif close < prior_low:
        close_state = "CLOSE_BELOW_PRIOR_RANGE"
    else:
        close_state = "CLOSE_INSIDE_PRIOR_RANGE"

    swept_high = high > prior_high and close <= prior_high
    swept_low = low < prior_low and close >= prior_low
    if swept_high and swept_low:
        sweep = "TWO_SIDED_SWEEP"
    elif swept_high:
        sweep = "UPSIDE_LIQUIDITY_SWEEP"
    elif swept_low:
        sweep = "DOWNSIDE_LIQUIDITY_SWEEP"
    else:
        sweep = "NONE"

    return {
        "lookback_bars": lookback,
        "prior_range_high": prior_high,
        "prior_range_low": prior_low,
        "close_state": close_state,
        "liquidity_sweep": sweep,
    }


def _failed_breakout(rows, *, lookback):
    if len(rows) < lookback + 2:
        return "INSUFFICIENT_HISTORY"
    base = rows[-(lookback + 2):-2]
    breakout = rows[-2]
    current = rows[-1]
    prior_high = max(row[2] for row in base)
    prior_low = min(row[3] for row in base)
    if breakout[4] > prior_high and current[4] <= prior_high:
        return "FAILED_UPSIDE_BREAKOUT"
    if breakout[4] < prior_low and current[4] >= prior_low:
        return "FAILED_DOWNSIDE_BREAKOUT"
    return "NONE"


def anchored_vwap(rows, *, anchor_index=0):
    rows = _validated_rows(rows)
    if isinstance(anchor_index, bool) or not isinstance(anchor_index, int) or not (0 <= anchor_index < len(rows)):
        raise DataArchitectureError("VWAP anchor invalid")
    selected = rows[anchor_index:]
    positive = [row for row in selected if row[5] > 0]
    if not positive:
        return {
            "status": "VOLUME_UNAVAILABLE",
            "value": None,
            "bars_used": 0,
            "reason": "NO_POSITIVE_VOLUME",
        }
    if len(positive) != len(selected):
        return {
            "status": "VOLUME_INCOMPLETE",
            "value": None,
            "bars_used": len(positive),
            "reason": "MIXED_ZERO_AND_POSITIVE_VOLUME",
        }
    numerator = sum(((row[2] + row[3] + row[4]) / 3.0) * row[5] for row in selected)
    denominator = sum(row[5] for row in selected)
    return {
        "status": "AVAILABLE",
        "value": round(numerator / denominator, 6),
        "bars_used": len(selected),
        "reason": None,
    }


def volume_confirmation(rows):
    rows = _validated_rows(rows)
    volumes = [row[5] for row in rows]
    positive = [value for value in volumes if value > 0]
    if not positive:
        return {
            "status": "VOLUME_NOT_APPLICABLE_OR_UNAVAILABLE",
            "latest_volume": volumes[-1],
            "median_positive_volume": None,
            "relative_to_median": None,
        }
    if len(positive) != len(volumes):
        status = "PARTIAL_VOLUME_HISTORY"
    else:
        status = "AVAILABLE"
    benchmark = median(positive[:-1] or positive)
    latest = volumes[-1]
    if latest <= 0:
        relative = "LATEST_ZERO_OR_UNAVAILABLE"
    elif latest > benchmark:
        relative = "ABOVE_MEDIAN"
    elif latest < benchmark:
        relative = "BELOW_MEDIAN"
    else:
        relative = "AT_MEDIAN"
    return {
        "status": status,
        "latest_volume": latest,
        "median_positive_volume": benchmark,
        "relative_to_median": relative,
    }


def derive_chart_evidence(rows, timeframe, *, swing_radius=2,
                          breakout_lookback=20, min_gap_pct=0.0):
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise DataArchitectureError("chart timeframe unsupported")
    rows = _validated_rows(rows, minimum=max(2 * swing_radius + 3, 4))
    swings = swing_points(rows, radius=swing_radius)
    latest = rows[-1]
    return {
        "schema": "5dr-derived-chart-evidence-v1",
        "timeframe": timeframe,
        "bar_count": len(rows),
        "first_timestamp": rows[0][0],
        "latest_timestamp": latest[0],
        "latest_close": latest[4],
        "trend_structure": _trend_from_swings(swings),
        "latest_swing_highs": swings["swing_highs"][-3:],
        "latest_swing_lows": swings["swing_lows"][-3:],
        "range_event": _range_event(rows, lookback=breakout_lookback),
        "failed_breakout": _failed_breakout(rows, lookback=min(breakout_lookback, len(rows) - 2)),
        "recent_gaps": _recent_gaps(rows, min_gap_pct=min_gap_pct),
        "volume_confirmation": volume_confirmation(rows),
        "anchored_vwap_from_first_bar": anchored_vwap(rows),
        "execution_only": timeframe == "5m",
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
    }


def derive_multi_timeframe_evidence(series_by_timeframe, *, swing_radius=2,
                                    breakout_lookback=20, min_gap_pct=0.0):
    if not isinstance(series_by_timeframe, dict) or not series_by_timeframe:
        raise DataArchitectureError("multi-timeframe chart input invalid")
    unknown = set(series_by_timeframe) - SUPPORTED_TIMEFRAMES
    if unknown:
        raise DataArchitectureError("multi-timeframe chart input unsupported")
    evidence = {
        timeframe: derive_chart_evidence(
            rows, timeframe,
            swing_radius=swing_radius,
            breakout_lookback=breakout_lookback,
            min_gap_pct=min_gap_pct,
        )
        for timeframe, rows in series_by_timeframe.items()
    }
    directional = [
        item["trend_structure"]["state"]
        for timeframe, item in evidence.items()
        if timeframe != "5m" and item["trend_structure"]["state"] in {"UPTREND_STRUCTURE", "DOWNTREND_STRUCTURE"}
    ]
    if not directional:
        alignment = "INSUFFICIENT_DIRECTIONAL_STRUCTURE"
    elif all(state == "UPTREND_STRUCTURE" for state in directional):
        alignment = "ALIGNED_UP"
    elif all(state == "DOWNTREND_STRUCTURE" for state in directional):
        alignment = "ALIGNED_DOWN"
    else:
        alignment = "MIXED"
    return {
        "schema": "5dr-multi-timeframe-chart-evidence-v1",
        "timeframes": evidence,
        "directional_alignment_excluding_5m": alignment,
        "five_minute_execution_only": "5m" in evidence,
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
    }
