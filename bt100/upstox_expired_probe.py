"""Bounded read-only probe for BT100 expired-derivative historical capability.

Maximum requests: 4.
1) available expired expiries
2) expired option contracts for one expiry
3) expired 30-minute candle sample for one option contract
4) date-specific OI-by-strike sample

No storage write, canonical write, trading action or inference call exists here.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE = "https://api.upstox.com/v2"
NIFTY = "NSE_INDEX|Nifty 50"
REQUEST_BUDGET = 4


class ProbeError(RuntimeError):
    pass


def _get(token, path, params=None):
    url = BASE + path
    if params:
        url += "?" + urlencode(params)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise ProbeError(f"Upstox unsuccessful response for {path}")
    return payload


def run(token):
    if not isinstance(token, str) or not token.strip():
        raise ProbeError("UPSTOX_ANALYTICS_TOKEN is missing")

    requests = 0
    expiries_payload = _get(token, "/expired-instruments/expiries", {"instrument_key": NIFTY})
    requests += 1
    expiries = expiries_payload.get("data")
    if not isinstance(expiries, list) or not expiries:
        raise ProbeError("expired expiry list empty")
    expiries = sorted(str(value) for value in expiries)
    probe_expiry = expiries[-1]

    contracts_payload = _get(
        token,
        "/expired-instruments/option/contract",
        {"instrument_key": NIFTY, "expiry_date": probe_expiry},
    )
    requests += 1
    contracts = contracts_payload.get("data")
    if not isinstance(contracts, list) or not contracts:
        raise ProbeError("expired option contracts empty")

    contract = next((row for row in contracts if row.get("instrument_type") in {"CE", "PE"}), None)
    if not isinstance(contract, dict):
        raise ProbeError("no CE/PE expired contract found")
    expired_key = contract.get("instrument_key")
    if not isinstance(expired_key, str) or not expired_key:
        raise ProbeError("expired instrument key missing")

    expiry_date = date.fromisoformat(probe_expiry)
    candle_from = (expiry_date - timedelta(days=10)).isoformat()
    encoded_key = quote(expired_key, safe="")
    candles_payload = _get(
        token,
        f"/expired-instruments/historical-candle/{encoded_key}/30minute/{probe_expiry}/{candle_from}",
    )
    requests += 1
    candles = candles_payload.get("data", {}).get("candles")
    if not isinstance(candles, list) or not candles:
        raise ProbeError("expired historical candles empty")
    rows_with_oi = sum(1 for row in candles if isinstance(row, list) and len(row) >= 7)

    oi_status = "PASSED"
    oi_rows = 0
    try:
        oi_payload = _get(
            token,
            "/market/oi",
            {"instrument_key": NIFTY, "expiry": probe_expiry, "date": probe_expiry},
        )
        oi_rows_raw = oi_payload.get("data", {}).get("call_put_oi_data_list")
        if not isinstance(oi_rows_raw, list) or not oi_rows_raw:
            oi_status = "PARTIAL"
        else:
            oi_rows = len(oi_rows_raw)
    except Exception:
        oi_status = "PARTIAL"
    requests += 1

    if requests != REQUEST_BUDGET:
        raise ProbeError("request budget mismatch")

    overall = "PASSED" if rows_with_oi > 0 and oi_status == "PASSED" else "PARTIAL"
    return {
        "schema": "bt100-upstox-expired-probe-v0",
        "status": overall,
        "request_budget": REQUEST_BUDGET,
        "requests_made": requests,
        "probe_expiry": probe_expiry,
        "available_expiry_count": len(expiries),
        "expired_option_contract_count": len(contracts),
        "sample_contract": {
            "instrument_type": contract.get("instrument_type"),
            "strike_price": contract.get("strike_price"),
            "expiry": contract.get("expiry"),
            "weekly": contract.get("weekly"),
        },
        "expired_30m_candle_count": len(candles),
        "expired_candles_with_oi": rows_with_oi,
        "historical_oi_by_strike_status": oi_status,
        "historical_oi_by_strike_rows": oi_rows,
        "read_only": True,
        "production_writes": 0,
        "production_neuron_calls": 0,
        "trading_enabled": False,
        "canonical_integration_enabled": False,
    }


def main():
    try:
        print(json.dumps(run(os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")), sort_keys=True, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({
            "schema": "bt100-upstox-expired-probe-v0",
            "status": "BLOCKED",
            "error_type": type(error).__name__,
            "request_budget": REQUEST_BUDGET,
            "read_only": True,
            "production_writes": 0,
            "production_neuron_calls": 0,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
        }, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
