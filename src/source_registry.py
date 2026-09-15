"""Allowlisted HTTP source fetcher for governed 5DR research evidence."""
import hashlib
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from src.event_evidence import EventSource


class SourceFetchError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class SourceFetchResult:
    ok: bool
    source_ref: str
    diagnostic: str


class AllowlistedSourceFetcher:
    def __init__(self, sources: tuple[EventSource, ...], opener=None):
        self._allowed = {source.url: source for source in sources}
        self._opener = opener or build_opener(NoRedirect())

    def __call__(self, source: EventSource) -> tuple[bool, str]:
        registered = self._allowed.get(source.url)
        if registered != source or not source.url.startswith("https://"):
            return False, ""
        request = Request(source.url, headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "EDGE-5DR-Research/1.0"}, method="GET")
        try:
            with self._opener.open(request, timeout=15) as response:
                raw = response.read(2_000_001)
                final_url = response.geturl()
            if final_url != source.url or len(raw) > 2_000_000 or not raw:
                return False, ""
            digest = hashlib.sha256(raw).hexdigest()
            return True, f"web:{source.url}#sha256={digest}"
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return False, ""
