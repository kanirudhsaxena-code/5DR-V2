"""NFO session-state validation for the isolated Upstox experiment.

Uses only the official read-only exchange-status endpoint. No trading/account
endpoints, databases, forecasts or production 5DR writers are reachable here.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from urllib.request import Request

from experiments.upstox_transport import CurlOpener
from phase1.upstox import PipelineError


STATUS_URL = "https://api.upstox.com/v2/market/status/NFO"
TIMINGS_URL = "https://api.upstox.com/v2/market/timings/{date}"
OPEN_STATUSES = {"NORMAL_OPEN", "PRE_OPEN_START", "PRE_OPEN_END"}
CLOSED_STATUSES = {"NORMAL_CLOSE", "CLOSING_START", "CLOSING_END"}
KNOWN_STATUSES = OPEN_STATUSES | CLOSED_STATUSES


def get_market_timings(token, trading_date: date, opener=None):
    """Return validated exchange timings for one date.

    Absence of NSE/NFO rows is authoritative evidence that the target date is
    not open for that segment. Provider/schema uncertainty fails closed.
    """
    if not token or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")
    if not isinstance(trading_date, date) or isinstance(trading_date, datetime):
        raise PipelineError("Market timings date is invalid")
    request = Request(
        TIMINGS_URL.format(date=trading_date.isoformat()),
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + token.strip(),
        },
        method="GET",
    )
    transport = opener or CurlOpener(max_bytes=256_000)
    try:
        with transport.open(request, timeout=20) as response:
            raw = response.read(256_001)
    except Exception as error:
        if isinstance(error, PipelineError):
            raise
        raise PipelineError("Market timings request failed") from None
    if len(raw) > 256_000:
        raise PipelineError("Market timings response exceeds size limit")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise PipelineError("Invalid market timings JSON") from None
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise PipelineError("Unexpected market timings schema")
    data = payload.get("data")
    if not isinstance(data, list):
        raise PipelineError("Unexpected market timings schema")
    exchanges = {}
    for row in data:
        if not isinstance(row, dict):
            raise PipelineError("Unexpected market timings schema")
        exchange = row.get("exchange")
        start = row.get("start_time")
        end = row.get("end_time")
        if (
            not isinstance(exchange, str)
            or not exchange.strip()
            or isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or start <= 0
            or end <= start
        ):
            raise PipelineError("Unexpected market timings schema")
        exchanges[exchange.strip().upper()] = {
            "exchange": exchange.strip().upper(),
            "start_time": int(start),
            "end_time": int(end),
        }
    return {
        "date": trading_date.isoformat(),
        "exchanges": exchanges,
        "source_path": f"/v2/market/timings/{trading_date.isoformat()}",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def get_nfo_market_status(token, opener=None):
    if not token or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")
    request = Request(
        STATUS_URL,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + token.strip(),
        },
        method="GET",
    )
    transport = opener or CurlOpener(max_bytes=256_000)
    try:
        with transport.open(request, timeout=20) as response:
            raw = response.read(256_001)
    except Exception as error:
        # Preserve PipelineError if introduced by a caller, otherwise withhold
        # transport/provider details from user-facing diagnostics.
        if isinstance(error, PipelineError):
            raise
        raise PipelineError("Market status request failed") from None
    if len(raw) > 256_000:
        raise PipelineError("Market status response exceeds size limit")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise PipelineError("Invalid market status JSON") from None
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise PipelineError("Unexpected market status schema")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("exchange") != "NFO":
        raise PipelineError("Unexpected market status schema")
    status = data.get("status")
    updated = data.get("last_updated")
    if status not in KNOWN_STATUSES or isinstance(updated, bool) or not isinstance(updated, (int, float)) or updated <= 0:
        raise PipelineError("Unexpected market status schema")
    updated_at = datetime.fromtimestamp(float(updated) / 1000.0, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    if updated_at > now.replace(microsecond=0) and (updated_at - now).total_seconds() > 300:
        raise PipelineError("Market status timestamp is in the future")
    if (now - updated_at).total_seconds() > 7 * 24 * 3600:
        raise PipelineError("Market status is stale")
    return {
        "exchange": "NFO",
        "status": status,
        "last_updated": updated_at.isoformat(),
        "received_at": now.isoformat(),
        "source_path": "/v2/market/status/NFO",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def select_session_valid_expiry(expiries, today: date, market_status: str):
    if market_status not in KNOWN_STATUSES:
        raise PipelineError("Unknown NFO market status")
    parsed = sorted({date.fromisoformat(value) for value in expiries if date.fromisoformat(value) >= today})
    if not parsed:
        raise PipelineError("No active NIFTY expiries returned")
    if parsed[0] == today and market_status in CLOSED_STATUSES:
        parsed = parsed[1:]
    if not parsed:
        raise PipelineError("No session-valid NIFTY expiry returned")
    return parsed[0].isoformat()
