"""Strict read-only endpoint registry for the 5DR Upstox quantitative experiment.

No request is executed here. The registry exists so future acquisition code can only
construct documented market-information requests and cannot drift into trading,
portfolio, funds, user/account, or order endpoints.
"""
from datetime import date
from urllib.parse import quote

from phase1.upstox import NIFTY, PipelineError

ENDPOINTS = {
    "ltp_v3": {"method": "GET", "path": "/v3/market-quote/ltp", "required": {"instrument_key"}, "optional": set()},
    "full_quote_v3": {"method": "GET", "path": "/v3/market-quote/quotes", "required": {"instrument_key"}, "optional": set()},
    "option_contracts": {"method": "GET", "path": "/v2/option/contract", "required": {"instrument_key"}, "optional": set()},
    "option_chain": {"method": "GET", "path": "/v2/option/chain", "required": {"instrument_key", "expiry_date"}, "optional": set()},
    "fii": {"method": "GET", "path": "/v2/market/fii", "required": {"data_type", "interval"}, "optional": {"from"}},
    "dii": {"method": "GET", "path": "/v2/market/dii", "required": {"data_type", "interval"}, "optional": {"from"}},
    "oi": {"method": "GET", "path": "/v2/market/oi", "required": {"instrument_key", "expiry", "date"}, "optional": set()},
    "change_oi": {"method": "GET", "path": "/v2/market/change-oi", "required": {"instrument_key", "expiry", "date", "interval"}, "optional": set()},
    "max_pain": {"method": "GET", "path": "/v2/market/max-pain", "required": {"instrument_key", "expiry", "date", "bucket_interval"}, "optional": set()},
    "pcr": {"method": "GET", "path": "/v2/market/pcr", "required": {"instrument_key", "expiry", "date", "bucket_interval"}, "optional": set()},
}

FII_TYPES = {"NSE_FO|INDEX_FUTURES", "NSE_FO|STOCK_FUTURES", "NSE_FO|INDEX_OPTIONS", "NSE_FO|STOCK_OPTIONS", "NSE_EQ|CASH"}
DII_TYPES = {"NSE_EQ|CASH"}


def _iso(value, field):
    if not isinstance(value, str):
        raise PipelineError(f"{field} invalid")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise PipelineError(f"{field} invalid") from None


def validate_request(name, params):
    spec = ENDPOINTS.get(name)
    if spec is None:
        raise PipelineError("Endpoint is not permitted")
    if spec["method"] != "GET":
        raise PipelineError("Non-GET endpoint refused")
    if not isinstance(params, dict):
        raise PipelineError("Endpoint parameters invalid")
    keys = set(params)
    if not spec["required"].issubset(keys) or not keys.issubset(spec["required"] | spec["optional"]):
        raise PipelineError("Endpoint parameters invalid")
    clean = dict(params)
    if name in {"option_contracts", "option_chain", "oi", "change_oi", "max_pain", "pcr"}:
        if clean.get("instrument_key") != NIFTY:
            raise PipelineError("Only NIFTY derivative analytics are permitted")
    if name == "option_chain":
        clean["expiry_date"] = _iso(clean["expiry_date"], "expiry")
    if name in {"oi", "change_oi", "max_pain", "pcr"}:
        clean["expiry"] = _iso(clean["expiry"], "expiry")
        clean["date"] = _iso(clean["date"], "date")
    if name == "change_oi":
        interval = clean["interval"]
        if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
            raise PipelineError("Change OI interval invalid")
    if name in {"max_pain", "pcr"}:
        bucket = clean["bucket_interval"]
        if isinstance(bucket, bool) or not isinstance(bucket, int) or bucket <= 0:
            raise PipelineError("Bucket interval invalid")
    if name in {"fii", "dii"}:
        allowed = FII_TYPES if name == "fii" else DII_TYPES
        data_type = clean.get("data_type")
        requested = data_type if isinstance(data_type, list) else [data_type]
        if not requested or any(value not in allowed for value in requested):
            raise PipelineError("Institutional data_type invalid")
        if clean.get("interval") not in {"1D", "1M"}:
            raise PipelineError("Institutional interval invalid")
        if "from" in clean:
            clean["from"] = _iso(clean["from"], "from")
    if name in {"ltp_v3", "full_quote_v3"}:
        value = clean.get("instrument_key")
        values = value if isinstance(value, list) else [value]
        if not values or len(values) > 500 or any(not isinstance(v, str) or not v for v in values):
            raise PipelineError("Quote instrument identity invalid")
    return {"name": name, "method": "GET", "path": spec["path"], "params": clean}


def historical_path(instrument_key, unit, interval, *, start=None, end=None, intraday=False):
    if not isinstance(instrument_key, str) or not instrument_key:
        raise PipelineError("Historical instrument identity invalid")
    if unit not in {"minutes", "hours", "days"}:
        raise PipelineError("Historical unit invalid")
    if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
        raise PipelineError("Historical interval invalid")
    encoded = quote(instrument_key, safe="")
    if intraday:
        if start is not None or end is not None:
            raise PipelineError("Intraday date parameters not permitted")
        return f"/v3/historical-candle/intraday/{encoded}/{unit}/{interval}"
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise PipelineError("Historical date range invalid")
    return f"/v3/historical-candle/{encoded}/{unit}/{interval}/{end.isoformat()}/{start.isoformat()}"


def assert_no_trading_surface():
    forbidden_fragments = ("/order", "/portfolio", "/fund", "/user", "/payment", "/gtt")
    for spec in ENDPOINTS.values():
        lowered = spec["path"].lower()
        if any(fragment in lowered for fragment in forbidden_fragments):
            raise PipelineError("Forbidden endpoint registered")
    return True
