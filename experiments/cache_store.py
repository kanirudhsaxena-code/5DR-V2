"""Provider-neutral cache-store contract for the experimental market-data backbone.

This module defines the durable-document boundary only. It performs no I/O and has no
knowledge of Upstox, Neon, canonical 5DR lifecycle tables, or trading/account surfaces.
"""
import hashlib
import json

from experiments.cache_reconcile import reconcile_candles
from experiments.data_contract import DataArchitectureError

DOCUMENT_SCHEMA = "market-cache-document-v1"
_VALIDATION_ENVELOPE = {
    "source_path": "/cache/validation",
    "sha256": "0" * 64,
    "received_at": "2000-01-01T00:00:00+00:00",
}
_DOCUMENT_FIELDS = {
    "schema", "series_id", "provider_id", "source_semantic", "record_count",
    "latest_timestamp", "dataset_sha256", "records", "audit_events",
    "document_sha256",
}
_AUDIT_FIELDS = {
    "event", "timestamp", "old_market_sha256", "new_market_sha256",
    "source_sha256", "received_at",
}


def _identity(value, field):
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"cache document {field} invalid")
    return value.strip()


def _hex64(value, field):
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value.lower())):
        raise DataArchitectureError(f"cache document {field} invalid")
    return value.lower()


def _validate_audit_event(event):
    if not isinstance(event, dict) or set(event) != _AUDIT_FIELDS:
        raise DataArchitectureError("cache audit event schema invalid")
    if event.get("event") != "PROVIDER_CORRECTION":
        raise DataArchitectureError("cache audit event type invalid")
    for field in ("timestamp", "received_at"):
        _identity(event.get(field), field)
    for field in ("old_market_sha256", "new_market_sha256", "source_sha256"):
        _hex64(event.get(field), field)
    return dict(event)


def _document_hash(document_without_hash):
    canonical = json.dumps(document_without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_records(records):
    # The reconciliation engine already contains the strict market/provenance validator.
    # Passing no incoming rows makes this a pure integrity check with no mutations.
    checked = reconcile_candles(records, [], _VALIDATION_ENVELOPE)
    return checked


def build_cache_document(series_id, reconciliation, *, provider_id,
                         source_semantic, prior_audit_events=()):
    series_id = _identity(series_id, "series_id")
    provider_id = _identity(provider_id, "provider_id")
    source_semantic = _identity(source_semantic, "source_semantic")
    if not isinstance(reconciliation, dict) or reconciliation.get("status") != "CACHE_RECONCILIATION_PASS":
        raise DataArchitectureError("cache reconciliation result invalid")
    records = reconciliation.get("records")
    if not isinstance(records, list):
        raise DataArchitectureError("cache reconciliation records invalid")
    checked = _validate_records(records)
    if checked["dataset_sha256"] != reconciliation.get("dataset_sha256"):
        raise DataArchitectureError("cache reconciliation dataset fingerprint mismatch")
    if checked["record_count"] != reconciliation.get("record_count"):
        raise DataArchitectureError("cache reconciliation record count mismatch")
    if checked["latest_timestamp"] != reconciliation.get("latest_timestamp"):
        raise DataArchitectureError("cache reconciliation latest timestamp mismatch")

    if not isinstance(prior_audit_events, (list, tuple)):
        raise DataArchitectureError("cache prior audit log invalid")
    current_events = reconciliation.get("audit_events")
    if not isinstance(current_events, list):
        raise DataArchitectureError("cache reconciliation audit log invalid")
    audit_events = [_validate_audit_event(event) for event in list(prior_audit_events) + current_events]

    body = {
        "schema": DOCUMENT_SCHEMA,
        "series_id": series_id,
        "provider_id": provider_id,
        "source_semantic": source_semantic,
        "record_count": checked["record_count"],
        "latest_timestamp": checked["latest_timestamp"],
        "dataset_sha256": checked["dataset_sha256"],
        "records": records,
        "audit_events": audit_events,
    }
    return {**body, "document_sha256": _document_hash(body)}


def validate_cache_document(document):
    if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
        raise DataArchitectureError("cache document schema invalid")
    if document.get("schema") != DOCUMENT_SCHEMA:
        raise DataArchitectureError("cache document version invalid")
    for field in ("series_id", "provider_id", "source_semantic"):
        _identity(document.get(field), field)
    _hex64(document.get("dataset_sha256"), "dataset_sha256")
    _hex64(document.get("document_sha256"), "document_sha256")
    if not isinstance(document.get("records"), list) or not isinstance(document.get("audit_events"), list):
        raise DataArchitectureError("cache document collections invalid")
    if isinstance(document.get("record_count"), bool) or not isinstance(document.get("record_count"), int) or document["record_count"] < 0:
        raise DataArchitectureError("cache document record count invalid")
    if document["latest_timestamp"] is not None and not isinstance(document["latest_timestamp"], str):
        raise DataArchitectureError("cache document latest timestamp invalid")

    checked = _validate_records(document["records"])
    if checked["record_count"] != document["record_count"]:
        raise DataArchitectureError("cache document record count mismatch")
    if checked["latest_timestamp"] != document["latest_timestamp"]:
        raise DataArchitectureError("cache document latest timestamp mismatch")
    if checked["dataset_sha256"] != document["dataset_sha256"]:
        raise DataArchitectureError("cache document dataset fingerprint mismatch")
    for event in document["audit_events"]:
        _validate_audit_event(event)

    body = {key: document[key] for key in document if key != "document_sha256"}
    if _document_hash(body) != document["document_sha256"]:
        raise DataArchitectureError("cache document fingerprint mismatch")
    return {
        "series_id": document["series_id"],
        "record_count": document["record_count"],
        "latest_timestamp": document["latest_timestamp"],
        "dataset_sha256": document["dataset_sha256"],
        "document_sha256": document["document_sha256"],
        "audit_event_count": len(document["audit_events"]),
    }


class MarketCacheStore:
    """Abstract storage boundary. Implementations must remain outside consumer logic."""

    backend_id = "ABSTRACT"

    def read_document(self, series_id):
        raise NotImplementedError

    def write_document(self, document, *, expected_document_sha256=None):
        raise NotImplementedError

    def list_series(self):
        raise NotImplementedError

    def recover(self):
        raise NotImplementedError

    def describe(self):
        return {"backend_id": self.backend_id, "provider_neutral": True}
