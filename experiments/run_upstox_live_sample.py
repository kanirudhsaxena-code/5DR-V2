# Experimental-only live verifier. No trading, no DB writes, no 5DR production writes.
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from experiments.upstox_sanitizer import sanitize_live_envelopes
from experiments.upstox_session import get_nfo_market_status, select_session_valid_expiry
from experiments.upstox_transport import CurlOpener
from phase1.upstox import NoRedirect, PipelineError, ReadOnlyClient, safe_failure

NIFTY = "NSE_INDEX|Nifty 50"
SAFE_ERROR_CODE = re.compile(r"^[A-Z0-9_]{1,40}$")


def _jwt_expired_without_exposing_claims(token):
    """Return True/False for JWT exp only; never return token content or claims."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return float(exp) <= datetime.now(timezone.utc).timestamp()
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return None


def _extract_error_codes(raw):
    """Extract only provider error-code identifiers; never provider messages."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        return []
    candidates = []
    if isinstance(payload, dict):
        for key in ("errorCode", "error_code", "code"):
            if key in payload:
                candidates.append(payload[key])
        errors = payload.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict):
                    for key in ("errorCode", "error_code", "code"):
                        if key in item:
                            candidates.append(item[key])
    result = []
    for value in candidates:
        text = str(value)
        if SAFE_ERROR_CODE.fullmatch(text) and text not in result:
            result.append(text)
    return result[:4]


def _safe_auth_probe(token, path, params):
    """urllib diagnostic kept only to identify the known transport rejection."""
    url = "https://api.upstox.com" + path + "?" + urlencode(params)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token.strip(),
        },
        method="GET",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            response.read(1)
            return {"http_status": int(response.status), "error_codes": []}
    except HTTPError as error:
        raw = error.read(65536)
        return {"http_status": int(error.code), "error_codes": _extract_error_codes(raw)}
    except (URLError, TimeoutError, OSError):
        return {"http_status": None, "error_codes": ["NETWORK_FAILED"]}


def _auth_diagnostics(token):
    result = {
        "jwt_expired_by_exp_claim": _jwt_expired_without_exposing_claims(token),
        "urllib_market_quote_ltp_v3": _safe_auth_probe(
            token,
            "/v3/market-quote/ltp",
            {"instrument_key": NIFTY},
        ),
    }
    time.sleep(1)
    result["urllib_option_contracts_v2"] = _safe_auth_probe(
        token,
        "/v2/option/contract",
        {"instrument_key": NIFTY},
    )
    return result


def main():
    stage = "INIT"
    token = os.getenv("UPSTOX_ANALYTICS_TOKEN")
    try:
        client = ReadOnlyClient(token, opener=CurlOpener())
        stage = "OPTION_CONTRACTS"
        contracts = client.contracts()
        expiries = sorted({row["expiry"] for row in contracts["payload"]["data"] if row.get("underlying_key") == NIFTY})
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()

        stage = "MARKET_STATUS"
        market_session = get_nfo_market_status(token)
        expiry = select_session_valid_expiry(expiries, today, market_session["status"])

        stage = "INTRADAY_CANDLES"
        intraday = client.intraday()
        stage = "OPTION_CHAIN"
        chain = client.chain(expiry)
        stage = "SANITIZE"
        result = sanitize_live_envelopes(contracts, intraday, chain, today, selected_expiry=expiry)
        result["market_session"] = {
            "exchange": market_session["exchange"],
            "status": market_session["status"],
            "last_updated": market_session["last_updated"],
        }
        result["provenance"]["market_status"] = {
            "source_path": market_session["source_path"],
            "sha256": market_session["sha256"],
            "received_at": market_session["received_at"],
        }
        result["transport"] = "curl"
        result["status"] = "LIVE_SAMPLE_PASSED"
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (PipelineError, ValueError, KeyError, TypeError, StopIteration) as error:
        code = safe_failure(error)
        output = {
            "status": "BLOCKED",
            "stage": stage,
            "diagnostic_code": code,
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "reason": "Authenticated acquisition or strict validation failed; provider payload, arbitrary exception text, and credentials withheld.",
        }
        if code == "AUTH_REJECTED" and token and token.strip():
            output["safe_auth_diagnostics"] = _auth_diagnostics(token)
        print(json.dumps(output, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
