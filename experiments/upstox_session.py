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
OPEN_STATUSES = {"NORMAL_OPEN", "PRE_OPEN_START", "PRE_OPEN_END"}
CLOSED_STATUSES = {"NORMAL_CLOSE", "CLOSING_START", "CLOSING_END"}
KNOWN_STATUSES = OPEN_STATUSES | CLOSED_STATUSES


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
