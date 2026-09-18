"""V3 quote-semantics correction for the live shadow bundle builder.

Upstox Full Market Quote V3 exposes `prev_close_price` as previous-session close and
`net_change` as absolute change from that close. The older experimental bundle helper
incorrectly treated `ohlc.close` as previous close; V3 `ohlc.close` is the live session
candle close. This wrapper swaps only that private normalization helper while reusing
the already-tested acquisition/bundle pipeline. No methodology or scoring logic changes.
"""
from __future__ import annotations

from experiments import live_shadow_bundle as _base
from experiments.data_contract import DataArchitectureError


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def v3_quote_snapshot(row):
    timestamp = _base._stamp(row.get("timestamp"))
    last = row.get("last_price")
    previous = row.get("prev_close_price")
    net_change = row.get("net_change")
    if not _is_number(previous) or not previous:
        if _is_number(last) and _is_number(net_change):
            previous = float(last) - float(net_change)
        else:
            previous = None
    change_pct = None
    if _is_number(last) and _is_number(previous) and previous:
        change_pct = round((float(last) - float(previous)) * 100.0 / float(previous), 6)
    return {
        "last_price": last,
        "volume": row.get("volume"),
        "open_interest": row.get("oi"),
        "previous_open_interest": row.get("previous_oi"),
        "average_price": row.get("average_price"),
        "net_change": net_change,
        "total_buy_quantity": row.get("total_buy_quantity"),
        "total_sell_quantity": row.get("total_sell_quantity"),
        "previous_close": previous,
        "change_pct_vs_previous_close": change_pct,
        "timestamp": timestamp.isoformat(),
    }


def build_live_shadow_bundle(token):
    original = _base._quote_snapshot
    try:
        _base._quote_snapshot = v3_quote_snapshot
        return _base.build_live_shadow_bundle(token)
    finally:
        _base._quote_snapshot = original


def build_public_judgment_summary(bundle):
    return _base.build_public_judgment_summary(bundle)
