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

from experiments.upstox_acquire import AcquisitionStageError, acquire_live_sample
from phase1.upstox import NoRedirect, safe_failure

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
    token = os.getenv("UPSTOX_ANALYTICS_TOKEN")
    try:
        result = acquire_live_sample(token)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except AcquisitionStageError as failure:
        code = safe_failure(failure.error)
        output = {
            "status": "BLOCKED",
            "stage": failure.stage,
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
