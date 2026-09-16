"""Governed external research contract for screenshot-free 5DR runs.

This module does not browse the web. A governed research executor supplies facts and
provenance; this layer validates, fingerprints and bounds that evidence before it may
enter the frozen 5DR evidence bundle. It never scores, forecasts, trades or writes
production state.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError

SCHEMA = "5dr-web-context-evidence-v1"
ALLOWED_SOURCE_SEMANTICS = frozenset({"OFFICIAL_WEB", "WEB_RESEARCH"})
DEFAULT_REQUIRED_EXTERNAL_CATEGORIES = (
    "DXY_RATES",
    "MACRO_EVENTS_GEOPOLITICS",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_FACT_CHARS = 4000


def _aware_utc(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} missing")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataArchitectureError(f"{field} naive")
    return parsed.astimezone(timezone.utc)


def _text(value, field, *, max_chars=None):
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"{field} invalid")
    clean = value.strip()
    if max_chars is not None and len(clean) > max_chars:
        raise DataArchitectureError(f"{field} too large")
    return clean


def _digest_payload(item):
    payload = {
        "category": item["category"],
        "source_semantic": item["source_semantic"],
        "source_reference": item["source_reference"],
        "source_sha256": item["source_sha256"],
        "authority": item["authority"],
        "observed_at": item["observed_at"],
        "retrieved_at": item["retrieved_at"],
        "fact_summary": item["fact_summary"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_web_context_item(*, category, source_semantic, source_reference,
                           source_sha256, authority, observed_at, retrieved_at,
                           fact_summary):
    category = _text(category, "web context category").upper()
    if source_semantic not in ALLOWED_SOURCE_SEMANTICS:
        raise DataArchitectureError("web context source semantic invalid")
    source_reference = _text(source_reference, "web context source reference", max_chars=2000)
    if not source_reference.startswith("https://"):
        raise DataArchitectureError("web context source must be https")
    if not isinstance(source_sha256, str) or not _SHA256_RE.fullmatch(source_sha256.lower()):
        raise DataArchitectureError("web context source digest invalid")
    authority = _text(authority, "web context authority", max_chars=128)
    observed = _aware_utc(observed_at, "web context observed_at")
    retrieved = _aware_utc(retrieved_at, "web context retrieved_at")
    if observed > retrieved:
        raise DataArchitectureError("web context observation after retrieval")
    fact_summary = _text(fact_summary, "web context fact summary", max_chars=_MAX_FACT_CHARS)

    item = {
        "context_schema": SCHEMA,
        "category": category,
        "source_semantic": source_semantic,
        "source_reference": source_reference,
        "source_sha256": source_sha256.lower(),
        "authority": authority,
        "observed_at": observed.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "fact_summary": fact_summary,
        "validation_status": "VALID",
    }
    item["research_sha256"] = _digest_payload(item)
    return item


def validate_web_context_item(item, *, frozen_at=None, max_age_seconds=None):
    if not isinstance(item, dict) or item.get("context_schema") != SCHEMA:
        raise DataArchitectureError("web context schema invalid")
    required = {
        "context_schema", "category", "source_semantic", "source_reference",
        "source_sha256", "authority", "observed_at", "retrieved_at",
        "fact_summary", "validation_status", "research_sha256",
    }
    if set(item) != required:
        raise DataArchitectureError("web context fields invalid")
    rebuilt = build_web_context_item(
        category=item["category"],
        source_semantic=item["source_semantic"],
        source_reference=item["source_reference"],
        source_sha256=item["source_sha256"],
        authority=item["authority"],
        observed_at=item["observed_at"],
        retrieved_at=item["retrieved_at"],
        fact_summary=item["fact_summary"],
    )
    if item.get("validation_status") != "VALID":
        raise DataArchitectureError("web context is not validated")
    if item.get("research_sha256") != rebuilt["research_sha256"]:
        raise DataArchitectureError("web context research fingerprint mismatch")

    if max_age_seconds is not None:
        if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
            raise DataArchitectureError("web context max age invalid")
        frozen = _aware_utc(frozen_at, "web context freeze")
        retrieved = _aware_utc(rebuilt["retrieved_at"], "web context retrieved_at")
        age = (frozen - retrieved).total_seconds()
        if age < -60 or age > max_age_seconds:
            raise DataArchitectureError("web context stale")
    return rebuilt


def prepare_web_context(items, *, frozen_at, required_categories=DEFAULT_REQUIRED_EXTERNAL_CATEGORIES,
                        max_age_seconds=86400):
    if not isinstance(items, (list, tuple)):
        raise DataArchitectureError("web context collection invalid")
    validated = [
        validate_web_context_item(item, frozen_at=frozen_at, max_age_seconds=max_age_seconds)
        for item in items
    ]
    categories = {item["category"] for item in validated}
    required = {str(value).strip().upper() for value in required_categories if str(value).strip()}
    missing = sorted(required - categories)
    if missing:
        raise DataArchitectureError(f"web context required categories missing: {missing}")
    fingerprints = [item["research_sha256"] for item in validated]
    if len(fingerprints) != len(set(fingerprints)):
        raise DataArchitectureError("duplicate web context evidence")
    return validated
