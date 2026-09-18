"""5DR-only structured quantitative reader on top of the proven curl transport.

The client is intentionally upstream of 5DR reasoning. It exposes only documented
GET market-data endpoints and only for an explicit approved 5DR instrument set.
No order, account, portfolio, funds, database, lifecycle or forecast surface exists.
"""
import hashlib
import json
import time
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from experiments.upstox_endpoints import historical_path, validate_request
from experiments.upstox_quality import validate_nonnegative, validate_ohlc, validate_price
from experiments.upstox_transport import CurlOpener
from phase1.upstox import BASE, NIFTY, PipelineError

INDIA_VIX = "NSE_INDEX|India VIX"
MAX_RESPONSE_BYTES = 8_000_000


def _query_pairs(params):
    pairs = []
    for key, value in params.items():
        if isinstance(value, list):
            if key == "instrument_key":
                pairs.append((key, ",".join(value)))
            elif key == "data_type":
                pairs.extend((key, item) for item in value)
            else:
                raise PipelineError("List query parameter not permitted")
        else:
            pairs.append((key, value))
    return pairs


def _validate_envelope_payload(payload):
    if not isinstance(payload, dict) or payload.get("status") != "success" or "data" not in payload:
        raise PipelineError("Unexpected Upstox response schema")


def _validate_candle_envelope(envelope):
    data = envelope["payload"]["data"]
    rows = data.get("candles") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise PipelineError("Candle array missing")
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 7:
            raise PipelineError(f"Candle schema mismatch at index {index}")
        try:
            stamp = datetime.fromisoformat(row[0])
        except (TypeError, ValueError):
            raise PipelineError(f"Candle timestamp invalid at index {index}") from None
        if stamp.tzinfo is None or stamp in seen:
            raise PipelineError(f"Naive or duplicate candle timestamp at index {index}")
        seen.add(stamp)
        try:
            validate_ohlc(row[1], row[2], row[3], row[4], volume=row[5], open_interest=row[6])
        except PipelineError as error:
            raise PipelineError(f"Candle validation failed at index {index}: {error}") from None
    envelope["validated_candles"] = len(rows)
    return envelope


def _canonical_expiry(value):
    """Normalize only the two provider-observed/documented unambiguous date formats.

    Upstox requests use ISO YYYY-MM-DD. Live OI/change-OI responses on 16 Sep 2026
    returned DD-MM-YYYY. Both are accepted only when they parse to an exact date; all
    other forms fail closed.
    """
    if not isinstance(value, str) or not value:
        raise PipelineError("Option analytics expiry invalid")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, "%d-%m-%Y").date().isoformat()
    except ValueError:
        raise PipelineError("Option analytics expiry invalid") from None


class QuantReadOnlyClient:
    def __init__(self, token, approved_instruments, opener=None, sleep=time.sleep):
        if not isinstance(token, str) or not token.strip():
            raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")
        if not isinstance(approved_instruments, (set, frozenset)) or not approved_instruments:
            raise PipelineError("Approved instrument set missing")
        if any(not isinstance(key, str) or not key for key in approved_instruments):
            raise PipelineError("Approved instrument identity invalid")
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
            raise PipelineError("Instrument request empty or duplicated")
        if any(key not in self._approved for key in values):
            raise PipelineError("Instrument is outside approved 5DR universe")
        return values

    def _get(self, path, params=None):
        params = dict(params or {})
        query = urlencode(_query_pairs(params)) if params else ""
        url = BASE + path + ("?" + query if query else "")
        for attempt in range(3):
            self._sleep(1)
            request = Request(url, headers={"Accept": "application/json", "Authorization": "Bearer " + self._token}, method="GET")
            try:
                with self._opener.open(request, timeout=20) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise PipelineError("Response exceeds size limit")
                payload = json.loads(raw)
                _validate_envelope_payload(payload)
                return {"received_at": datetime.now(timezone.utc).isoformat(), "source_path": path, "parameters": params, "sha256": hashlib.sha256(raw).hexdigest(), "payload": payload}
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
                raise PipelineError("Invalid JSON response") from None
        raise PipelineError("Retry budget exhausted")

    def endpoint(self, name, params):
        request = validate_request(name, params)
        if name in {"ltp_v3", "full_quote_v3"}:
            self._require_approved(request["params"]["instrument_key"])
        return self._get(request["path"], request["params"])

    def full_quotes(self, keys):
        requested = self._require_approved(keys)
        envelope = self.endpoint("full_quote_v3", {"instrument_key": requested})
        data = envelope["payload"]["data"]
        if not isinstance(data, dict) or not data:
            raise PipelineError("Full quote data missing")
        returned = []
        for quote in data.values():
            if not isinstance(quote, dict):
                raise PipelineError("Full quote row invalid")
            token = quote.get("instrument_token")
            if not isinstance(token, str) or not token:
                raise PipelineError("Full quote instrument identity missing")
            returned.append(token)
            validate_price(quote.get("last_price"), "last_price")
            if quote.get("volume") is not None:
                validate_nonnegative(quote["volume"], "volume")
            if quote.get("oi") is not None:
                validate_nonnegative(quote["oi"], "open_interest")
            if not isinstance(quote.get("timestamp"), str) or not quote["timestamp"]:
                raise PipelineError("Full quote timestamp missing")
        if len(returned) != len(set(returned)) or set(returned) != set(requested):
            raise PipelineError("Full quote identity set mismatch")
        envelope["validated_instrument_tokens"] = sorted(returned)
        return envelope

    def intraday(self, instrument_key, unit, interval):
        key = self._require_approved(instrument_key)[0]
        path = historical_path(key, unit, interval, intraday=True)
        return _validate_candle_envelope(self._get(path))

    def historical(self, instrument_key, unit, interval, start, end):
        key = self._require_approved(instrument_key)[0]
        path = historical_path(key, unit, interval, start=start, end=end, intraday=False)
        return _validate_candle_envelope(self._get(path))

    def institutional(self, name, data_types, interval="1D"):
        if name not in {"fii", "dii"}:
            raise PipelineError("Institutional endpoint invalid")
        requested = list(data_types) if isinstance(data_types, (list, tuple)) else [data_types]
        params = {"data_type": requested if len(requested) > 1 else requested[0], "interval": interval}
        envelope = self.endpoint(name, params)
        data = envelope["payload"]["data"]
        if not isinstance(data, dict) or set(data) != set(requested):
            raise PipelineError("Institutional response identity mismatch")
        for key in requested:
            rows = data[key]
            if not isinstance(rows, list) or not rows:
                raise PipelineError("Institutional response empty")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("time_stamp"), int) or row["time_stamp"] <= 0:
                    raise PipelineError("Institutional timestamp invalid")
                for field in ("buy_amount", "sell_amount", "buy_contracts", "sell_contracts", "oi_contracts"):
                    if row.get(field) is not None:
                        validate_nonnegative(row[field], field)
        envelope["validated_data_types"] = sorted(requested)
        return envelope

    def option_analytics(self, name, *, expiry, date_value, interval=None, bucket_interval=None):
        params = {"instrument_key": NIFTY, "expiry": expiry, "date": date_value}
        if name == "change_oi":
            params["interval"] = interval
        elif name in {"pcr", "max_pain"}:
            params["bucket_interval"] = bucket_interval
        elif name != "oi":
            raise PipelineError("Option analytics endpoint invalid")
        envelope = self.endpoint(name, params)
        data = envelope["payload"]["data"]
        if not isinstance(data, dict) or not data:
            raise PipelineError("Option analytics response missing")
        if name == "oi":
            if _canonical_expiry(data.get("expiry")) != expiry:
                raise PipelineError("OI expiry mismatch")
            rows = data.get("call_put_oi_data_list")
            if not isinstance(rows, list) or not rows:
                raise PipelineError("OI strike data missing")
            validate_nonnegative(data.get("total_puts"), "total_puts")
            validate_nonnegative(data.get("total_calls"), "total_calls")
            for row in rows:
                validate_price(row.get("strike_price"), "strike_price")
                validate_nonnegative(row.get("call_oi"), "call_oi")
                validate_nonnegative(row.get("put_oi"), "put_oi")
            envelope["validated_expiry"] = expiry
        elif name == "change_oi":
            rows = data.get("call_put_oi_data_list")
            if not isinstance(rows, list) or not rows:
                raise PipelineError("Change OI strike data missing")
            if _canonical_expiry(data.get("expiry")) != expiry:
                raise PipelineError("Change OI expiry mismatch")
            envelope["validated_expiry"] = expiry
        else:
            if data.get("instrument_key") != NIFTY:
                raise PipelineError("Option analytics underlying mismatch")
            if not isinstance(data.get("insights"), list):
                raise PipelineError("Option analytics insights missing")
        return envelope
