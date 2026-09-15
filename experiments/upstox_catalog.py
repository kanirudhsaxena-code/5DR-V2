"""Strict public instrument-master reader for the isolated 5DR Upstox experiment."""
import gzip
import hashlib
import io
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request

from experiments.upstox_transport import CurlOpener
from phase1.upstox import PipelineError

GLOBAL_URL = "https://assets.upstox.com/market-quote/instruments/exchange/global.json.gz"
NSE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
ALLOWED_URLS = {GLOBAL_URL, NSE_URL}
MAX_COMPRESSED_BYTES = 30_000_000
MAX_DECOMPRESSED_BYTES = 150_000_000


class PublicInstrumentCatalog:
    def __init__(self, opener=None):
        self._opener = opener or CurlOpener(max_bytes=MAX_COMPRESSED_BYTES + 1)

    def fetch(self, url):
        if url not in ALLOWED_URLS:
            raise PipelineError("Instrument catalog URL is not permitted")
        request = Request(url, headers={"Accept": "application/gzip, application/json"}, method="GET")
        try:
            with self._opener.open(request, timeout=30) as response:
                raw = response.read(MAX_COMPRESSED_BYTES + 1)
        except HTTPError as error:
            raise PipelineError(f"Instrument catalog HTTP {error.code}; response withheld") from None
        except (URLError, TimeoutError, OSError):
            raise PipelineError("Instrument catalog network request failed") from None
        if len(raw) > MAX_COMPRESSED_BYTES:
            raise PipelineError("Instrument catalog compressed size exceeded")
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as stream:
                decoded = stream.read(MAX_DECOMPRESSED_BYTES + 1)
        except (OSError, EOFError):
            raise PipelineError("Instrument catalog gzip invalid") from None
        if len(decoded) > MAX_DECOMPRESSED_BYTES:
            raise PipelineError("Instrument catalog decompressed size exceeded")
        try:
            payload = json.loads(decoded)
        except (ValueError, UnicodeError):
            raise PipelineError("Instrument catalog JSON invalid") from None
        if not isinstance(payload, list) or not payload:
            raise PipelineError("Instrument catalog schema invalid")
        return {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "source_url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "records": payload,
        }

    def global_instruments(self):
        return self.fetch(GLOBAL_URL)

    def nse_instruments(self):
        return self.fetch(NSE_URL)
