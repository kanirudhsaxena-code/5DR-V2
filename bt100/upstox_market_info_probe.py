"""Bounded read-only probe for historical market-information analytics.

This intentionally avoids expired-instrument endpoints. It verifies whether the
connected Analytics token can retrieve point-in-time OI and change-OI for a recent
completed session using a relative current-month expiry.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.upstox.com/v2"
NIFTY = "NSE_INDEX|Nifty 50"
PROBE_DATE = "2026-05-07"
REQUEST_BUDGET = 2


def _get(token, path, params):
    url = BASE + path + "?" + urlencode(params)
    req = Request(url, headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }, method="GET")
    try:
        with urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        diagnostic = {"http_status": error.code}
        try:
            body = json.loads(error.read().decode("utf-8"))
            errors = body.get("errors") if isinstance(body, dict) else None
            if isinstance(errors, list) and errors and isinstance(errors[0], dict):
                diagnostic["provider_code"] = errors[0].get("errorCode") or errors[0].get("error_code")
                diagnostic["provider_message"] = errors[0].get("message")
            elif isinstance(body, dict):
                diagnostic["provider_code"] = body.get("errorCode") or body.get("error_code")
                diagnostic["provider_message"] = body.get("message")
        except Exception:
            pass
        raise RuntimeError(json.dumps(diagnostic, sort_keys=True)) from None


def run(token):
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("UPSTOX_ANALYTICS_TOKEN missing")

    oi = _get(token, "/market/oi", {
        "instrument_key": NIFTY,
        "expiry": "2026-05-29",
        "date": PROBE_DATE,
    })
    oi_rows = oi.get("data", {}).get("call_put_oi_data_list")
    if oi.get("status") != "success" or not isinstance(oi_rows, list) or not oi_rows:
        raise RuntimeError("historical OI response invalid")

    change = _get(token, "/market/change-oi", {
        "instrument_key": NIFTY,
        "expiry": "current_month",
        "date": PROBE_DATE,
        "interval": 2,
    })
    change_rows = change.get("data", {}).get("call_put_oi_data_list")
    if change.get("status") != "success" or not isinstance(change_rows, list) or not change_rows:
        raise RuntimeError("historical change-OI response invalid")

    return {
        "schema": "bt100-upstox-market-info-probe-v0",
        "status": "PASSED",
        "probe_date": PROBE_DATE,
        "expiry_selector": "2026-05-29",
        "oi_rows": len(oi_rows),
        "change_oi_rows": len(change_rows),
        "request_budget": REQUEST_BUDGET,
        "requests_made": REQUEST_BUDGET,
        "read_only": True,
        "production_writes": 0,
        "production_neuron_calls": 0,
        "trading_enabled": False,
    }


def main():
    try:
        print(json.dumps(run(os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")), sort_keys=True, indent=2))
        return 0
    except Exception as error:
        diagnostic = {}
        try:
            decoded = json.loads(str(error))
            if isinstance(decoded, dict):
                diagnostic = decoded
        except Exception:
            diagnostic = {"error_type": type(error).__name__}
        print(json.dumps({
            "schema": "bt100-upstox-market-info-probe-v0",
            "status": "BLOCKED",
            **diagnostic,
            "probe_date": PROBE_DATE,
            "request_budget": REQUEST_BUDGET,
            "read_only": True,
            "production_writes": 0,
            "production_neuron_calls": 0,
            "trading_enabled": False,
        }, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
