"""ASCENT N3 G1 feasibility: isolated, authenticated, READ-ONLY Upstox probe.
Only uses existing 5DR-V2 transport and GitHub secret. Never publishes a forecast,
places broker orders, mutates existing market tables, or emits token/raw payload.
"""
import hashlib
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request
from zoneinfo import ZoneInfo
from experiments.upstox_transport import CurlOpener

BASE = "https://api.upstox.com"
NIFTY = "NSE_INDEX|Nifty 50"
IST = ZoneInfo("Asia/Kolkata")
MAX_BYTES = 5_000_000

class ProbeError(Exception):
    pass

def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def validate_contracts(items, expiry=None):
    if not isinstance(items, list) or not items:
        raise ProbeError("CONTRACTS_EMPTY")
    valid = []
    for c in items:
        if not isinstance(c, dict):
            continue
        if c.get("underlying_key") != NIFTY or c.get("instrument_type") not in ("CE", "PE"):
            continue
        if not finite(c.get("strike_price")) or not finite(c.get("lot_size")) or c["lot_size"] <= 0:
            continue
        if not isinstance(c.get("instrument_key"), str) or not c["instrument_key"].startswith("NSE_FO|"):
            continue
        try:
            contract_expiry = date.fromisoformat(c["expiry"])
        except (KeyError, ValueError, TypeError):
            continue
        if expiry and contract_expiry != expiry:
            continue
        valid.append(c)
    if {c["instrument_type"] for c in valid} != {"CE", "PE"}:
        raise ProbeError("CE_PE_COVERAGE_MISSING")
    return valid

def expired_dates(values, today):
    if not isinstance(values, list):
        raise ProbeError("EXPIRIES_SCHEMA")
    try:
        dates = sorted({date.fromisoformat(x) for x in values if isinstance(x, str) and x})
    except ValueError as exc:
        raise ProbeError("EXPIRIES_FORMAT") from exc
    dates = [d for d in dates if d < today]
    if not dates:
        raise ProbeError("NO_EXPIRED_EXPIRY")
    return dates

def summarize_candles(rows, start, end, require_volume=False):
    if not isinstance(rows, list) or not rows:
        raise ProbeError("CANDLES_EMPTY")
    times = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6 or any(not finite(v) for v in row[1:5]):
            raise ProbeError("CANDLE_OHLC_SCHEMA")
        if require_volume and not finite(row[5]):
            raise ProbeError("CANDLE_VOLUME_SCHEMA")
        o, h, l, c = row[1:5]
        if h < max(o, c, l) or l > min(o, c) or l < 0:
            raise ProbeError("CANDLE_OHLC_INCONSISTENT")
        try:
            ts = datetime.fromisoformat(row[0])
        except (TypeError, ValueError) as exc:
            raise ProbeError("CANDLE_TIME_SCHEMA") from exc
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise ProbeError("CANDLE_TIMEZONE_MISSING")
        if not start <= ts.astimezone(IST).date() <= end:
            raise ProbeError("CANDLE_OUT_OF_RANGE")
        times.append(ts)
    if len(times) != len(set(times)):
        raise ProbeError("DUPLICATE_CANDLE")
    return {"count": len(times),
            "first_ist": min(times).astimezone(IST).isoformat(),
            "last_ist": max(times).astimezone(IST).isoformat(),
            "precision": "candle_start; intrabar high_low order unknown"}

class ReadOnlyBroker:
    def __init__(self, token, opener=None):
        if not token or not token.strip():
            raise ProbeError("EXISTING_SECRET_NOT_AVAILABLE")
        self.token = token.strip()
        self.opener = opener or CurlOpener()
        self.receipts = []

    def get(self, lane, path, params=None):
        url = BASE + path + ("?" + urlencode(params) if params else "")
        request = Request(url, method="GET", headers={
            "Accept": "application/json", "Authorization": "Bearer " + self.token})
        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(MAX_BYTES + 1)
        except HTTPError as exc:
            raise ProbeError("HTTP_" + str(exc.code)) from None
        except (URLError, OSError, TimeoutError):
            raise ProbeError("NETWORK_FAILURE") from None
        if len(raw) > MAX_BYTES:
            raise ProbeError("RESPONSE_OVERSIZED")
        try:
            body = json.loads(raw)
        except (UnicodeDecodeError, ValueError):
            raise ProbeError("JSON_INVALID") from None
        if not isinstance(body, dict) or body.get("status") != "success" or "data" not in body:
            errors = body.get("errors") if isinstance(body, dict) else None
            if isinstance(errors, list) and errors and isinstance(errors[0], dict) and errors[0].get("error_code") == "UDAPI1149":
                raise ProbeError("PLUS_ACCESS_REJECTED")
            raise ProbeError("RESPONSE_NOT_SUCCESS")
        self.receipts.append({
            "lane": lane, "method": "GET", "path": path,
            "received_at_utc": datetime.now(timezone.utc).isoformat(),
            "payload_sha256": hashlib.sha256(raw).hexdigest()})
        return body["data"]

def probe_quote(b):
    data = b.get("nifty_quote", "/v3/market-quote/ltp", {"instrument_key": NIFTY})
    if not isinstance(data, dict) or not data:
        raise ProbeError("QUOTE_EMPTY")
    return {"instruments": len(data)}

def probe_spot_1m(b, today):
    start = today - timedelta(days=7)
    path = f"/v3/historical-candle/{quote(NIFTY, safe='')}/minutes/1/{today}/{start}"
    data = b.get("nifty_1m", path)
    if not isinstance(data, dict):
        raise ProbeError("SPOT_HISTORY_SCHEMA")
    return summarize_candles(data.get("candles"), start, today)

def probe_current_contracts(b):
    data = b.get("nifty_option_contracts", "/v2/option/contract", {"instrument_key": NIFTY})
    valid = validate_contracts(data)
    return {"count": len(valid), "ce": sum(x["instrument_type"] == "CE" for x in valid),
            "pe": sum(x["instrument_type"] == "PE" for x in valid),
            "expiries": len({x["expiry"] for x in valid})}

def probe_expiries(b, today):
    data = b.get("expired_expiries", "/v2/expired-instruments/expiries", {"instrument_key": NIFTY})
    dates = expired_dates(data, today)
    return {"count": len(dates), "first": str(dates[0]), "latest": str(dates[-1])}

def probe_expired_ce_pe(b, expiry):
    data = b.get("expired_contracts", "/v2/expired-instruments/option/contract",
                 {"instrument_key": NIFTY, "expiry_date": str(expiry)})
    contracts = validate_contracts(data, expiry=expiry)
    mid = sorted(x["strike_price"] for x in contracts)[len(contracts) // 2]
    ce = min((c for c in contracts if c["instrument_type"] == "CE"),
             key=lambda x: (abs(x["strike_price"] - mid), x["instrument_key"]))
    pe = min((c for c in contracts if c["instrument_type"] == "PE"),
             key=lambda x: (abs(x["strike_price"] - ce["strike_price"]), x["instrument_key"]))
    out = {"expiry": str(expiry)}
    for side, contract in (("ce", ce), ("pe", pe)):
        path = f"/v2/expired-instruments/historical-candle/{quote(contract['instrument_key'],safe='')}/1minute/{expiry}/{expiry}"
        data = b.get("expired_" + side + "_one_minute", path)
        if not isinstance(data, dict):
            raise ProbeError("EXPIRED_CANDLES_SCHEMA")
        out[side] = summarize_candles(data.get("candles"), expiry, expiry, require_volume=True)
        out[side]["strike"] = contract["strike_price"]
        out[side]["lot"] = contract["lot_size"]
    return out

def main():
    today = datetime.now(IST).date()
    report = {"schema": "ascent-n3-g1-readonly-source-v1",
              "run_id": os.getenv("GITHUB_RUN_ID", "LOCAL"),
              "as_of_ist": str(today), "read_only": True, "trading_enabled": False,
              "stages": {}, "receipts": [], "source_probe_pass": False,
              "n3_engine_ack": "UNTESTED", "notes": [
                  "Past 5DR evidence does not prove N3 producer-to-consumer ACK.",
                  "OHLC high/low sequencing cannot be inferred from one bar."]}
    broker = None
    def stage(label, call):
        try:
            value = call()
            report["stages"][label] = {"status": "PASS", **value}
            return value
        except ProbeError as exc:
            report["stages"][label] = {"status": "FAIL", "code": str(exc)}
        except Exception:
            report["stages"][label] = {"status": "FAIL", "code": "UNEXPECTED_SCHEMA"}
        return None
    try:
        broker = ReadOnlyBroker(os.environ.get("UPSTOX_ANALYTICS_TOKEN", ""))
        stage("nifty_quote", lambda: probe_quote(broker))
        stage("nifty_1m", lambda: probe_spot_1m(broker, today))
        stage("current_ce_pe_contracts", lambda: probe_current_contracts(broker))
        d = stage("expired_expiries", lambda: probe_expiries(broker, today))
        if d:
            stage("expired_ce_pe_1m", lambda: probe_expired_ce_pe(broker, date.fromisoformat(d["latest"])))
        else:
            report["stages"]["expired_ce_pe_1m"] = {"status": "NOT_RUN"}
    except ProbeError as exc:
        report["stages"]["authentication"] = {"status": "FAIL", "code": str(exc)}
    report["receipts"] = broker.receipts if broker else []
    report["source_probe_pass"] = all(report["stages"].get(k,{}).get("status") == "PASS" for k in
         ("nifty_quote", "nifty_1m", "current_ce_pe_contracts", "expired_expiries", "expired_ce_pe_1m"))
    target = Path(os.environ.get("G1_OUTPUT_FILE", ".g1/evidence.json"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("G1_SOURCE_PROBE=" + ("PASS" if report["source_probe_pass"] else "BLOCKED"))
    for k, v in report["stages"].items():
        print("G1_CHECK=" + k + ":" + v["status"] + (":" + v["code"] if "code" in v else ""))
    return 0 if report["source_probe_pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
