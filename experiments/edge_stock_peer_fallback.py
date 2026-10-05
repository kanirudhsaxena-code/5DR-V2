"""Reputable-secondary peer-cohort fallback for EDGE_STOCK.

The fallback activates only when the structured provider peer lane is unavailable.
It produces evidence, not investment judgment.
"""
import hashlib
import re
from html.parser import HTMLParser
from urllib.request import Request

from experiments.data_contract import DataArchitectureError, build_record
from experiments.edge_stock_source_registry import build_source_health
from experiments.upstox_transport import CurlOpener


class _PeerParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_peer_heading = False
        self.market_links = []
        self.current_href = None
        self.current_text = []
        self._heading_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"h2","h3"}:
            self._heading_depth += 1
        if tag == "a":
            self.current_href = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        text = (data or "").strip()
        if text:
            if self._heading_depth and "peer comparison" in text.lower():
                self.in_peer_heading = True
            if self.current_href is not None:
                self.current_text.append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href is not None:
            href = self.current_href
            text = " ".join(self.current_text).strip()
            if self.in_peer_heading and href.startswith("/market/") and text:
                self.market_links.append((href, text))
            self.current_href = None
            self.current_text = []
        if tag in {"h2","h3"} and self._heading_depth:
            self._heading_depth -= 1


class _IndustryParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.current_href = None
        self.current_text = []
        self.companies = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.in_table = True
        if self.in_table and tag == "a":
            self.current_href = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None and data and data.strip():
            self.current_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self.current_href is not None:
            href = self.current_href or ""
            text = " ".join(self.current_text).strip()
            match = re.fullmatch(r"/company/([A-Z0-9_.-]+)(?:/consolidated)?/?", href)
            if match and text:
                symbol = match.group(1)
                self.companies.append({"symbol": symbol, "name": text})
            self.current_href = None
            self.current_text = []
        if tag == "table":
            self.in_table = False


def _fetch(url, opener):
    req = Request(url, headers={
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "MDOS-EDGE-Stock-Research/1.0",
    }, method="GET")
    with opener.open(req, timeout=20) as response:
        body = response.read(2_000_001)
    if not body or len(body) > 2_000_000:
        raise DataArchitectureError("peer fallback response size invalid")
    return body


def acquire_peer_fallback(stock_identity, *, acquisition_timestamp, opener=None,
                          max_peers=12):
    if not isinstance(stock_identity, dict) or stock_identity.get("kind") != "STOCK":
        raise DataArchitectureError("peer fallback stock identity invalid")
    symbol = stock_identity.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise DataArchitectureError("peer fallback symbol missing")
    if isinstance(max_peers, bool) or not isinstance(max_peers, int) or not 3 <= max_peers <= 25:
        raise DataArchitectureError("peer fallback max peers invalid")
    opener = opener or CurlOpener(max_bytes=2_000_001)

    company_url = f"https://www.screener.in/company/{symbol}/consolidated/"
    company_body = _fetch(company_url, opener)
    company_parser = _PeerParser()
    company_parser.feed(company_body.decode("utf-8", errors="ignore"))
    if not company_parser.market_links:
        raise DataArchitectureError("peer fallback industry identity missing")
    # Deepest industry link is the most specific classification.
    industry_href, industry_name = max(
        company_parser.market_links,
        key=lambda item: item[0].count("/"),
    )
    industry_url = "https://www.screener.in" + industry_href
    industry_body = _fetch(industry_url, opener)
    industry_parser = _IndustryParser()
    industry_parser.feed(industry_body.decode("utf-8", errors="ignore"))
    seen = set()
    cohort = []
    for row in industry_parser.companies:
        if row["symbol"] == symbol or row["symbol"] in seen:
            continue
        seen.add(row["symbol"])
        cohort.append(row)
        if len(cohort) >= max_peers:
            break
    if len(cohort) < 3:
        raise DataArchitectureError("peer fallback cohort insufficient")

    source_digest = hashlib.sha256(company_body + b"|" + industry_body).hexdigest()
    health = build_source_health(
        source_name="SCREENER_PEER_COHORT",
        url=industry_url,
        checked_at=acquisition_timestamp,
        success=True,
        recovery_attempt="UPSTOX_COMPETITORS_UNAVAILABLE",
        fallback="SCREENER_INDUSTRY_COHORT",
        final_status="RECOVERED_VIA_FALLBACK",
    )
    return build_record(
        provider_id="WEB_RESEARCH",
        source_semantic="WEB_RESEARCH",
        variable_id="STOCK_PEERS",
        consumer="EDGE_STOCK",
        subject=stock_identity,
        metric="reputable_secondary_industry_peer_cohort",
        values={
            "reconciliation_status": "RECOVERED_VIA_FALLBACK",
            "industry": industry_name,
            "peer_cohort": cohort,
            "peer_count": len(cohort),
            "provider_gap": "UPSTOX_COMPETITORS_UNAVAILABLE",
            "source_health": health,
            "judgment_applied": False,
        },
        timeframe="snapshot",
        provider_timestamp=acquisition_timestamp,
        acquisition_timestamp=acquisition_timestamp,
        freshness_status="LIVE",
        source_reference=industry_url,
        source_sha256=source_digest,
    )
