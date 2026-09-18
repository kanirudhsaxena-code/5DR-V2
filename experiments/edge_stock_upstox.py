"""Read-only Upstox market/fundamentals client for EDGE_STOCK.

This client is intentionally separate from the validated 5DR QuantReadOnlyClient so
stock-specific endpoints can evolve without changing frozen 5DR behavior. Only GET
market-information/fundamentals/news endpoints are reachable. No order, account,
portfolio, funds, payment, GTT or trading surface exists.
"""
import hashlib
import json
import time
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request

from experiments.data_contract import DataArchitectureError
from experiments.upstox_transport import CurlOpener
from phase1.upstox import BASE, PipelineError

MAX_RESPONSE_BYTES = 8_000_000
FORBIDDEN_FRAGMENTS = ("/order", "/portfolio", "/funds", "/user/", "/payment", "/gtt")

FUNDAMENTAL_PATHS = {
    "profile": "/v2/fundamentals/{isin}/profile",
    "balance_sheet": "/v2/fundamentals/{isin}/balance-sheet",
    "cash_flow": "/v2/fundamentals/{isin}/cash-flow",
    "income_statement": "/v2/fundamentals/{isin}/income-statement",
    "share_holdings": "/v2/fundamentals/{isin}/share-holdings",
    "key_ratios": "/v2/fundamentals/{isin}/key-ratios",
    "corporate_actions": "/v2/fundamentals/{isin}/corporate-actions",
    "competitors": "/v2/fundamentals/{isin}/competitors",
}


def _iso(value, field):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    raise DataArchitectureError(f"{field} invalid")


def _clean_isin(isin):
    if not isinstance(isin, str) or not isin.strip():
        raise DataArchitectureError("ISIN invalid")
    clean = isin.strip().upper()
    if len(clean) != 12 or not clean.isalnum():
        raise DataArchitectureError("ISIN invalid")
    return clean


def _validate_path(path):
    lowered = path.lower()
    if any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS):
        raise PipelineError("Forbidden endpoint refused")
    if not path.startswith(("/v2/fundamentals/", "/v2/news", "/v2/option/", "/v3/market-quote/", "/v3/historical-candle/")):
        raise PipelineError("Endpoint outside EDGE_STOCK read-only allowlist")
    return path


class EdgeStockReadOnlyClient:
    def __init__(self, token, *, approved_instruments, opener=None, sleep=time.sleep):
        if not isinstance(token, str) or not token.strip():
            raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")
        if not isinstance(approved_instruments, (set, frozenset)) or not approved_instruments:
            raise DataArchitectureError("approved EDGE_STOCK instruments missing")
        if any(not isinstance(key, str) or not key for key in approved_instruments):
            raise DataArchitectureError("approved EDGE_STOCK instrument invalid")
        self._token = token.strip()
        self._approved = frozenset(approved_instruments)
        self._opener = opener or CurlOpener()
        self._sleep = sleep

    @property
    def approved_instruments(self):
        return self._approved

    def _require_approved(self, keys):
        values = list(keys) if isinstance(keys, (list, tuple, set, frozenset)) else [keys]
        if not values or len(values) != len(set(values)):
            raise DataArchitectureError("EDGE_STOCK instrument request invalid")
        if any(value not in self._approved for value in values):
            raise DataArchitectureError("instrument outside EDGE_STOCK approved universe")
        return values

    def _get(self, path, params=None):
        path = _validate_path(path)
        params = dict(params or {})
        query_string = urlencode(params, doseq=True) if params else ""
        url = BASE + path + (("?" + query_string) if query_string else "")
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer " + self._token,
            },
            method="GET",
        )
        for attempt in range(3):
            self._sleep(1)
            try:
                with self._opener.open(request, timeout=20) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise PipelineError("EDGE_STOCK response exceeds size limit")
                payload = json.loads(raw)
                if not isinstance(payload, dict) or payload.get("status") != "success" or "data" not in payload:
                    raise PipelineError("Unexpected EDGE_STOCK Upstox response schema")
                return {
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "source_path": path,
                    "parameters": params,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "payload": payload,
                }
            except HTTPError as error:
                if error.code in (401, 403):
                    raise PipelineError("Analytics Token expired, invalid, or lacks access") from None
                if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise PipelineError(f"Upstox HTTP {error.code}; response withheld") from None
                self._sleep(2 ** (attempt + 1))
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise PipelineError("Upstox network request failed") from None
                self._sleep(2 ** (attempt + 1))
            except (ValueError, UnicodeError):
                raise PipelineError("Invalid Upstox JSON response") from None
        raise PipelineError("EDGE_STOCK retry budget exhausted")

    def full_quotes(self, keys):
        requested = self._require_approved(keys)
        envelope = self._get("/v3/market-quote/quotes", {"instrument_key": ",".join(requested)})
        data = envelope["payload"]["data"]
        if not isinstance(data, dict) or not data:
            raise PipelineError("EDGE_STOCK quote data missing")
        returned = {
            row.get("instrument_token")
            for row in data.values()
            if isinstance(row, dict)
        }
        if returned != set(requested):
            raise PipelineError("EDGE_STOCK quote identity mismatch")
        return envelope

    def historical(self, instrument_key, unit, interval, start, end):
        key = self._require_approved(instrument_key)[0]
        if unit not in {"minutes", "hours", "days"}:
            raise DataArchitectureError("EDGE_STOCK historical unit invalid")
        if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
            raise DataArchitectureError("EDGE_STOCK historical interval invalid")
        if unit == "days" and interval != 1:
            raise DataArchitectureError("EDGE_STOCK daily interval invalid")
        start_iso = _iso(start, "historical start")
        end_iso = _iso(end, "historical end")
        if start_iso > end_iso:
            raise DataArchitectureError("EDGE_STOCK historical range reversed")
        encoded = quote(key, safe="")
        path = f"/v3/historical-candle/{encoded}/{unit}/{interval}/{end_iso}/{start_iso}"
        return self._get(path)

    def intraday(self, instrument_key, unit, interval):
        key = self._require_approved(instrument_key)[0]
        if unit not in {"minutes", "hours"}:
            raise DataArchitectureError("EDGE_STOCK intraday unit invalid")
        if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
            raise DataArchitectureError("EDGE_STOCK intraday interval invalid")
        encoded = quote(key, safe="")
        return self._get(f"/v3/historical-candle/intraday/{encoded}/{unit}/{interval}")

    def fundamental(self, name, isin, **params):
        if name not in FUNDAMENTAL_PATHS:
            raise DataArchitectureError("EDGE_STOCK fundamental endpoint invalid")
        clean_isin = _clean_isin(isin)
        allowed = {}
        if name in {"balance_sheet", "cash_flow"}:
            if "type" in params:
                if params["type"] not in {"consolidated", "standalone"}:
                    raise DataArchitectureError("fundamental statement type invalid")
                allowed["type"] = params["type"]
            if "fs" in params:
                if not isinstance(params["fs"], bool):
                    raise DataArchitectureError("fundamental fs invalid")
                allowed["fs"] = str(params["fs"]).lower()
        elif name == "income_statement":
            if "type" in params:
                if params["type"] not in {"consolidated", "standalone"}:
                    raise DataArchitectureError("income statement type invalid")
                allowed["type"] = params["type"]
            if "time_period" in params:
                if params["time_period"] not in {"yearly", "quarterly"}:
                    raise DataArchitectureError("income statement time period invalid")
                allowed["time_period"] = params["time_period"]
            if "fs" in params:
                if not isinstance(params["fs"], bool):
                    raise DataArchitectureError("income statement fs invalid")
                allowed["fs"] = str(params["fs"]).lower()
        elif params:
            raise DataArchitectureError("fundamental endpoint parameters not permitted")
        path = FUNDAMENTAL_PATHS[name].format(isin=clean_isin)
        return self._get(path, allowed)

    def news(self, instrument_key, *, page_number=1, page_size=100):
        key = self._require_approved(instrument_key)[0]
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (page_number, page_size)):
            raise DataArchitectureError("news pagination invalid")
        if not 1 <= page_number <= 100 or not 1 <= page_size <= 100:
            raise DataArchitectureError("news pagination outside limits")
        return self._get("/v2/news", {
            "category": "instrument_keys",
            "instrument_keys": key,
            "page_number": page_number,
            "page_size": page_size,
        })

    def option_contracts(self, underlying_key, *, expiry_date=None):
        key = self._require_approved(underlying_key)[0]
        params = {"instrument_key": key}
        if expiry_date is not None:
            params["expiry_date"] = _iso(expiry_date, "option expiry")
        envelope = self._get("/v2/option/contract", params)
        rows = envelope["payload"]["data"]
        if not isinstance(rows, list):
            raise PipelineError("option contracts payload invalid")
        for row in rows:
            if not isinstance(row, dict) or row.get("underlying_key") != key:
                raise PipelineError("option contract underlying mismatch")
        return envelope

    def option_chain(self, underlying_key, expiry_date):
        key = self._require_approved(underlying_key)[0]
        expiry = _iso(expiry_date, "option expiry")
        envelope = self._get("/v2/option/chain", {
            "instrument_key": key,
            "expiry_date": expiry,
        })
        rows = envelope["payload"]["data"]
        if not isinstance(rows, list) or not rows:
            raise PipelineError("option chain payload missing")
        for row in rows:
            if not isinstance(row, dict) or row.get("underlying_key") != key or row.get("expiry") != expiry:
                raise PipelineError("option chain identity mismatch")
        return envelope


def assert_edge_stock_read_only_surface():
    for path in FUNDAMENTAL_PATHS.values():
        _validate_path(path.format(isin="INE000000001"))
    for path in (
        "/v2/news",
        "/v2/option/contract",
        "/v2/option/chain",
        "/v3/market-quote/quotes",
        "/v3/historical-candle/x/days/1/2026-09-18/2026-09-01",
    ):
        _validate_path(path)
    return True
