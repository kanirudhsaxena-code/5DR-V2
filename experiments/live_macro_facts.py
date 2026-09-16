"""Deterministic fact extraction for the governed V2.2.3 live-web lane.

The extractors are intentionally narrow. A source that is reachable but does not expose
an approved fact remains REFERENCE_ONLY; it is never converted to a neutral market
signal. No scoring, forecasting, persistence or trading occurs here.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

FACT_EXTRACTED = "FACT_EXTRACTED"
REFERENCE_ONLY = "REFERENCE_ONLY"


def _compact(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fed_h15(text):
    clean = _compact(text)
    facts = {}
    release = re.search(r"Release date:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", clean, re.I)
    if release:
        facts["release_date"] = release.group(1)

    anchor = re.search(r"Treasury constant maturities", clean, re.I)
    segment = clean[anchor.start():] if anchor else clean
    ten = re.search(r"\b10-year\s+((?:\d+(?:\.\d+)?\s+){1,12})", segment, re.I)
    if ten:
        values = [_float(v) for v in re.findall(r"\d+(?:\.\d+)?", ten.group(1))]
        values = [v for v in values if v is not None]
        if values:
            facts["treasury_10y_percent"] = values[-1]
            facts["treasury_10y_observation_count_in_visible_row"] = len(values)
    fed_funds = re.search(r"Federal funds \(effective\).*?((?:\d+(?:\.\d+)?\s+){1,12})", clean, re.I)
    if fed_funds:
        values = [_float(v) for v in re.findall(r"\d+(?:\.\d+)?", fed_funds.group(1))]
        values = [v for v in values if v is not None]
        if values:
            facts["effective_fed_funds_percent"] = values[-1]
    return facts


def _fed_calendar(text, now):
    clean = _compact(text)
    facts = {}
    month = now.strftime("%B")
    year = now.year
    # The official FOMC page groups meetings under a calendar year and month. Restrict
    # matching to the current month name and a two-day range.
    match = re.search(rf"\b{re.escape(month)}\b.*?\b(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\*?", clean, re.I)
    if match:
        start_day, end_day = int(match.group(1)), int(match.group(2))
        facts.update({
            "meeting_type": "FOMC",
            "meeting_start_date": f"{year:04d}-{now.month:02d}-{start_day:02d}",
            "meeting_end_date": f"{year:04d}-{now.month:02d}-{end_day:02d}",
            "decision_day_matches_retrieval_date": now.day == end_day,
        })
    # Some official calendar pages expose the release clock time.
    time_match = re.search(r"\b2:00\s*p\.m\.\b.*?FOMC\s+Meeting", clean, re.I)
    if time_match:
        facts["statement_time_et"] = "14:00"
    press = re.search(r"\b2:30\s*p\.m\.\b.*?FOMC\s+Press\s+Conference", clean, re.I)
    if press:
        facts["press_conference_time_et"] = "14:30"
    return facts


def _rbi_current_rates(text):
    clean = _compact(text)
    facts = {}
    repo = re.search(r"Policy\s+Repo\s+Rate\s*[:|]*\s*(\d+(?:\.\d+)?)%", clean, re.I)
    if repo:
        facts["policy_repo_rate_percent"] = float(repo.group(1))
    usd = re.search(r"INR\s*/\s*1\s*USD\s*[:|]*\s*(\d+(?:\.\d+)?)", clean, re.I)
    if usd:
        facts["rbi_displayed_usdinr"] = float(usd.group(1))
    as_at = re.search(r"As at\s+1\.00pm\s+of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", clean, re.I)
    if as_at:
        facts["rbi_displayed_usdinr_as_at"] = as_at.group(1)
    return facts


def extract_role_facts(role_name, visible_text, *, now):
    """Return a bounded, deterministic fact package for one governed web role."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("macro fact extraction requires timezone-aware now")
    if role_name == "RATES_REFERENCE":
        facts = _fed_h15(visible_text)
    elif role_name == "MACRO_CALENDAR":
        facts = _fed_calendar(visible_text, now)
    elif role_name == "INDIA_POLICY":
        facts = _rbi_current_rates(visible_text)
    else:
        facts = {}
    return {
        "fact_quality": FACT_EXTRACTED if facts else REFERENCE_ONLY,
        "facts": facts,
    }


def fact_summary_prefix(role_name, package):
    quality = package.get("fact_quality", REFERENCE_ONLY)
    facts = package.get("facts") if isinstance(package.get("facts"), dict) else {}
    encoded = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    return f"role={role_name}; fact_quality={quality}; facts_json={encoded};"
