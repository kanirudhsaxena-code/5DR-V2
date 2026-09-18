"""Exact stock and F&O identity resolution for the EDGE_STOCK consumer.

Pure validation only. No network, scoring, forecasting, persistence, account action,
or trading is performed here.
"""
from datetime import date, datetime, timezone

from experiments.data_contract import DataArchitectureError


def _as_date(value, field):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    raise DataArchitectureError(f"{field} invalid")


def resolve_nse_equity(rows, *, symbol=None, isin=None):
    if not isinstance(rows, list) or not rows:
        raise DataArchitectureError("NSE instrument master missing")
    if symbol is None and isin is None:
        raise DataArchitectureError("stock identity selector missing")
    if symbol is not None and (not isinstance(symbol, str) or not symbol.strip()):
        raise DataArchitectureError("stock symbol invalid")
    if isin is not None and (not isinstance(isin, str) or not isin.strip()):
        raise DataArchitectureError("stock ISIN invalid")
    symbol_key = symbol.strip().upper() if isinstance(symbol, str) else None
    isin_key = isin.strip().upper() if isinstance(isin, str) else None

    matches = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("exchange") != "NSE" or row.get("segment") != "NSE_EQ":
            continue
        if row.get("instrument_type") != "EQ":
            continue
        row_symbol = row.get("trading_symbol")
        row_isin = row.get("isin")
        if symbol_key is not None and (
            not isinstance(row_symbol, str) or row_symbol.upper() != symbol_key
        ):
            continue
        if isin_key is not None and (
            not isinstance(row_isin, str) or row_isin.upper() != isin_key
        ):
            continue
        matches.append(row)

    if len(matches) != 1:
        raise DataArchitectureError("stock identity ambiguous or missing")
    row = matches[0]
    instrument_key = row.get("instrument_key")
    trading_symbol = row.get("trading_symbol")
    name = row.get("name")
    row_isin = row.get("isin")
    if not all(isinstance(v, str) and v.strip() for v in (
        instrument_key, trading_symbol, name, row_isin
    )):
        raise DataArchitectureError("stock identity fields missing")
    if not instrument_key.startswith("NSE_EQ|"):
        raise DataArchitectureError("stock instrument key invalid")

    return {
        "kind": "STOCK",
        "id": row_isin.strip().upper(),
        "name": name.strip(),
        "exchange": "NSE",
        "segment": "NSE_EQ",
        "instrument_key": instrument_key.strip(),
        "symbol": trading_symbol.strip().upper(),
        "isin": row_isin.strip().upper(),
    }


def resolve_stock_fo_identity(rows, stock_identity, *, as_of):
    if not isinstance(rows, list) or not rows:
        raise DataArchitectureError("NSE instrument master missing")
    if not isinstance(stock_identity, dict):
        raise DataArchitectureError("stock identity missing")
    underlying_key = stock_identity.get("instrument_key")
    symbol = stock_identity.get("symbol")
    if not isinstance(underlying_key, str) or not underlying_key:
        raise DataArchitectureError("stock underlying key missing")
    as_of = _as_date(as_of, "F&O as-of date")

    derivatives = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("exchange") != "NSE" or row.get("segment") != "NSE_FO":
            continue
        if row.get("underlying_key") != underlying_key:
            continue
        instrument_type = row.get("instrument_type")
        if instrument_type not in {"FUT", "CE", "PE"}:
            continue
        expiry = _as_date(row.get("expiry"), "stock derivative expiry")
        if expiry < as_of:
            continue
        key = row.get("instrument_key")
        trading_symbol = row.get("trading_symbol")
        if not isinstance(key, str) or not key.startswith("NSE_FO|"):
            raise DataArchitectureError("stock derivative key invalid")
        if not isinstance(trading_symbol, str) or not trading_symbol:
            raise DataArchitectureError("stock derivative symbol invalid")
        derivatives.append({
            "instrument_type": instrument_type,
            "expiry": expiry.isoformat(),
            "instrument_key": key,
            "trading_symbol": trading_symbol,
        })

    if not derivatives:
        return {
            "fo_eligible": False,
            "underlying_key": underlying_key,
            "symbol": symbol,
            "active_expiries": [],
            "nearest_expiry": None,
            "has_future": False,
            "has_calls": False,
            "has_puts": False,
        }

    expiries = sorted({row["expiry"] for row in derivatives})
    nearest = expiries[0]
    nearest_rows = [row for row in derivatives if row["expiry"] == nearest]
    has_future = any(row["instrument_type"] == "FUT" for row in nearest_rows)
    has_calls = any(row["instrument_type"] == "CE" for row in nearest_rows)
    has_puts = any(row["instrument_type"] == "PE" for row in nearest_rows)
    if not (has_calls and has_puts):
        raise DataArchitectureError("stock F&O chain incomplete for nearest expiry")
    return {
        "fo_eligible": True,
        "underlying_key": underlying_key,
        "symbol": symbol,
        "active_expiries": expiries,
        "nearest_expiry": nearest,
        "has_future": has_future,
        "has_calls": has_calls,
        "has_puts": has_puts,
    }
