"""Live governed web-context acquisition for screenshot-free 5DR shadow runs.

This executor fetches a small allowlisted set of public HTTPS sources, extracts a
bounded visible-text excerpt, fingerprints the exact response body, and emits the
existing V2.2.3 web-context contract. It does not score, forecast, trade, persist
production state, or infer that a failed source means 'no event'.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request

from experiments.data_contract import DataArchitectureError
from experiments.upstox_transport import CurlOpener
from experiments.web_context import build_web_context_item, prepare_web_context


@dataclass(frozen=True)
class WebRole:
    role: str
    category: str
    source_semantic: str
    authority: str
    urls: tuple[str, ...]
    keywords: tuple[str, ...]


ROLE_SOURCES = (
    WebRole(
        "DXY_OWNER_REFERENCE",
        "DXY_RATES",
        "WEB_RESEARCH",
        "INDEX_PROVIDER",
        ("https://www.ice.com/fixed-income-data-services/index-solutions/currency-indices",),
        ("U.S. Dollar Index", "DXY"),
    ),
    WebRole(
        "RATES_REFERENCE",
        "DXY_RATES",
        "OFFICIAL_WEB",
        "CENTRAL_BANK",
        ("https://www.federalreserve.gov/releases/h15/",),
        ("Selected Interest Rates", "Federal funds"),
    ),
    WebRole(
        "MACRO_CALENDAR",
        "MACRO_EVENTS_GEOPOLITICS",
        "OFFICIAL_WEB",
        "CENTRAL_BANK",
        (
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            "https://www.federalreserve.gov/newsevents/calendar.htm",
        ),
        ("FOMC", "Meeting"),
    ),
    WebRole(
        "INDIA_POLICY",
        "MACRO_EVENTS_GEOPOLITICS",
        "OFFICIAL_WEB",
        "CENTRAL_BANK",
        (
            "https://www.rbi.org.in/",
            "https://m.rbi.org.in/",
        ),
        ("Policy Repo Rate", "Monetary Policy"),
    ),
    WebRole(
        "GEOPOLITICS_CONTEXT",
        "MACRO_EVENTS_GEOPOLITICS",
        "OFFICIAL_WEB",
        "GOVERNMENT_OR_MULTILATERAL",
        (
            "https://www.state.gov/press-releases/",
            "https://www.mea.gov.in/press-releases.htm",
        ),
        ("Press", "Release"),
    ),
)

REQUIRED_ROLES = frozenset(role.role for role in ROLE_SOURCES)
_MAX_BODY_BYTES = 1_500_000
_MAX_EXCERPT_CHARS = 3500
_MIN_EXCERPT_CHARS = 80


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._ignored = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "svg", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "svg", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        if not self._ignored and data and data.strip():
            self._parts.append(data.strip())

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def _excerpt(body: bytes, role: WebRole) -> str:
    parser = _VisibleText()
    try:
        parser.feed(body.decode("utf-8", errors="ignore"))
    except (ValueError, UnicodeError) as error:
        raise DataArchitectureError("web source html parse failed") from error
    text = parser.text()
    if len(text) < _MIN_EXCERPT_CHARS:
        raise DataArchitectureError("web source visible text insufficient")
    lower = text.lower()
    hits = [lower.find(keyword.lower()) for keyword in role.keywords]
    hits = [index for index in hits if index >= 0]
    if not hits:
        raise DataArchitectureError(f"web source role keyword missing: {role.role}")
    start = max(0, min(hits) - 300)
    excerpt = text[start:start + _MAX_EXCERPT_CHARS].strip()
    if len(excerpt) < _MIN_EXCERPT_CHARS:
        raise DataArchitectureError("web source excerpt insufficient")
    return excerpt


def _fetch_one(role: WebRole, opener, now: datetime):
    failures = []
    for url in role.urls:
        if not url.startswith("https://"):
            failures.append("NON_HTTPS")
            continue
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "5DR-V223-Research/1.0",
            },
            method="GET",
        )
        try:
            with opener.open(request, timeout=20) as response:
                body = response.read(_MAX_BODY_BYTES + 1)
            if not body or len(body) > _MAX_BODY_BYTES:
                raise DataArchitectureError("web source response size invalid")
            excerpt = _excerpt(body, role)
            digest = hashlib.sha256(body).hexdigest()
            stamp = now.astimezone(timezone.utc).isoformat()
            return build_web_context_item(
                category=role.category,
                source_semantic=role.source_semantic,
                source_reference=url,
                source_sha256=digest,
                authority=role.authority,
                observed_at=stamp,
                retrieved_at=stamp,
                fact_summary=f"role={role.role}; source_excerpt={excerpt}",
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, DataArchitectureError):
            failures.append("FETCH_OR_VALIDATE_FAILED")
    raise DataArchitectureError(f"required live web role unavailable: {role.role}; attempts={len(failures)}")


def collect_live_web_context(*, now=None, opener=None, roles=ROLE_SOURCES):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("live web context now must be timezone-aware")
    opener = opener or CurlOpener(max_bytes=_MAX_BODY_BYTES + 1)
    if not isinstance(roles, (tuple, list)) or not roles:
        raise DataArchitectureError("live web roles missing")
    role_names = [role.role for role in roles]
    if len(role_names) != len(set(role_names)):
        raise DataArchitectureError("duplicate live web role")
    missing_roles = sorted(REQUIRED_ROLES - set(role_names))
    if missing_roles:
        raise DataArchitectureError(f"required live web roles missing: {missing_roles}")

    items = [_fetch_one(role, opener, now) for role in roles]
    prepared = prepare_web_context(
        items,
        frozen_at=now,
        required_categories={"DXY_RATES", "MACRO_EVENTS_GEOPOLITICS"},
        max_age_seconds=900,
    )
    return {
        "status": "5DR_LIVE_WEB_CONTEXT_PASSED",
        "roles": role_names,
        "items": prepared,
        "screenshot_required": False,
        "directional_score_assigned": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "trading_enabled": False,
    }
