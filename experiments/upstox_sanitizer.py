"""Pure sanitizer/validator for experimental Upstox market-data envelopes.

No network, database, forecast, lifecycle, or trading operations exist here.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from phase1.upstox import NIFTY, PipelineError, validate_candles


def _dec(value, field):
    if isinstance(value, bool) or value is None:
        raise PipelineError(f"{field} missing")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise PipelineError(f"{field} invalid") from None
    if not result.is_finite():
        raise PipelineError(f"{field} invalid")
    return result


def _number(value, field):
    result = _dec(value, field)
    if result < 0:
        raise PipelineError(f"{field} negative")
    return int(result) if result == result.to_integral() else float(result)


def sanitize_live_envelopes(contracts, intraday, chain, today: date, selected_expiry=None, allow_empty_intraday=False):
    rows = contracts["payload"]["data"]
    if not isinstance(rows, list) or not rows:
        raise PipelineError("Contract array missing")
    by_key = {}
    expiries = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("underlying_key") != NIFTY:
            continue
        expiry = row.get("expiry")
        key = row.get("instrument_key")
        if not isinstance(expiry, str) or not isinstance(key, str) or not key:
            raise PipelineError("Contract identity missing")
        if date.fromisoformat(expiry) >= today:
            expiries.add(expiry)
            if key in by_key:
                raise PipelineError("Duplicate option instrument key")
            by_key[key] = row
    if not expiries:
        raise PipelineError("No active NIFTY expiries returned")
    if selected_expiry is None:
        selected_expiry = sorted(expiries)[0]
    else:
        if not isinstance(selected_expiry, str):
            raise PipelineError("Selected expiry invalid")
        date.fromisoformat(selected_expiry)
        if selected_expiry not in expiries:
            raise PipelineError("Selected expiry not in contract master")

    validate_candles(intraday)
    candle_rows = intraday["payload"]["data"]["candles"]
    if not candle_rows and not allow_empty_intraday:
        raise PipelineError("Intraday candles empty")
    latest = max(candle_rows, key=lambda row: datetime.fromisoformat(row[0])) if candle_rows else None

    chain_rows = chain["payload"]["data"]
    if not isinstance(chain_rows, list) or not chain_rows:
        raise PipelineError("Option chain is empty")
    normalized = []
    spots = set()
    seen = set()
    for row in chain_rows:
        if row.get("expiry") != selected_expiry or row.get("underlying_key") != NIFTY:
            raise PipelineError("Chain contract identity mismatch")
        strike = _dec(row.get("strike_price"), "strike")
        spot = _dec(row.get("underlying_spot_price"), "underlying spot")
        if strike <= 0 or strike in seen or spot <= 0:
            raise PipelineError("Invalid or duplicate strike")
        seen.add(strike)
        spots.add(spot)
        normalized.append((strike, row))
    if len(spots) != 1:
        raise PipelineError("Inconsistent underlying spot across chain")
    spot = next(iter(spots))
    normalized.sort(key=lambda item: item[0])
    atm = min(range(len(normalized)), key=lambda i: abs(normalized[i][0] - spot))
    sample_rows = normalized[max(0, atm - 2): min(len(normalized), atm + 3)]

    sample = []
    for strike, row in sample_rows:
        out = {"strike": _number(strike, "strike")}
        for side_name, field_name, expected in (("CE", "call_options", "CE"), ("PE", "put_options", "PE")):
            leg = row.get(field_name)
            if not isinstance(leg, dict):
                raise PipelineError(f"{side_name} leg missing")
            key = leg.get("instrument_key")
            contract = by_key.get(key)
            if not contract:
                raise PipelineError(f"{side_name} contract not found")
            if contract.get("expiry") != selected_expiry or contract.get("instrument_type") != expected:
                raise PipelineError(f"{side_name} identity mismatch")
            if _dec(contract.get("strike_price"), "contract strike") != strike:
                raise PipelineError(f"{side_name} strike mismatch")
            market = leg.get("market_data")
            if not isinstance(market, dict):
                raise PipelineError(f"{side_name} market data missing")
            out[side_name] = {
                "instrument_key": key,
                "trading_symbol": contract.get("trading_symbol"),
                "ltp": _number(market.get("ltp"), f"{side_name} ltp"),
                "oi": _number(market.get("oi"), f"{side_name} oi"),
                "volume": _number(market.get("volume"), f"{side_name} volume"),
            }
        sample.append(out)

    return {
        "read_only": True,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
        "underlying": NIFTY,
        "available_expiries": sorted(expiries)[:8],
        "selected_expiry": selected_expiry,
        "underlying_spot_price": _number(spot, "underlying spot"),
        "latest_intraday_candle": None if latest is None else {
            "timestamp": latest[0], "open": latest[1], "high": latest[2],
            "low": latest[3], "close": latest[4], "volume": latest[5],
            "open_interest": latest[6],
        },
        "intraday_availability": "UNAVAILABLE_MARKET_CLOSED" if latest is None else "AVAILABLE",
        "sample_strikes": sample,
        "provenance": {
            "contracts": {"source_path": contracts["source_path"], "sha256": contracts["sha256"], "received_at": contracts["received_at"]},
            "intraday": {"source_path": intraday["source_path"], "sha256": intraday["sha256"], "received_at": intraday["received_at"]},
            "option_chain": {"source_path": chain["source_path"], "sha256": chain["sha256"], "received_at": chain["received_at"]},
        },
    }
