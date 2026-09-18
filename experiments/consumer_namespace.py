"""Consumer namespace primitives for the shared MDOS evidence backbone.

This module contains identity/isolation mechanics only. It performs no acquisition,
scoring, forecasting, persistence, broker/account action, or trading.
"""
import hashlib
import json
from copy import deepcopy

from experiments.data_contract import DataArchitectureError
from experiments.data_requirements import CONSUMERS


def _identity(value, field):
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"{field} invalid")
    return value.strip()


def normalize_consumer(consumer):
    value = _identity(consumer, "consumer").upper()
    if value not in CONSUMERS:
        raise DataArchitectureError("consumer invalid")
    return value


def consumer_namespace(consumer, subject_id):
    consumer = normalize_consumer(consumer)
    subject_id = _identity(subject_id, "subject id")
    return f"{consumer}:{subject_id}"


def consumer_cache_key(*, consumer, provider_id, variable_id, subject_id, timeframe="none"):
    parts = [
        normalize_consumer(consumer),
        _identity(provider_id, "provider id").upper(),
        _identity(variable_id, "variable id").upper(),
        _identity(subject_id, "subject id").upper(),
        _identity(timeframe, "timeframe").upper(),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def build_run_ledger_entry(*, consumer, subject_id, run_id, status,
                           bundle_sha256=None, metadata=None):
    consumer = normalize_consumer(consumer)
    subject_id = _identity(subject_id, "subject id")
    run_id = _identity(run_id, "run id")
    status = _identity(status, "run status").upper()
    if bundle_sha256 is not None:
        if (not isinstance(bundle_sha256, str) or len(bundle_sha256) != 64 or
                any(c not in "0123456789abcdef" for c in bundle_sha256.lower())):
            raise DataArchitectureError("bundle fingerprint invalid")
        bundle_sha256 = bundle_sha256.lower()
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise DataArchitectureError("run metadata invalid")

    body = {
        "schema": "shared-consumer-run-ledger-entry-v1",
        "consumer": consumer,
        "subject_id": subject_id,
        "namespace": consumer_namespace(consumer, subject_id),
        "run_id": run_id,
        "status": status,
        "bundle_sha256": bundle_sha256,
        "metadata": deepcopy(metadata),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    body["entry_sha256"] = hashlib.sha256(canonical).hexdigest()
    return body


class ConsumerRunLedger:
    """In-memory isolation guard suitable for testing/adapters.

    Durable storage adapters may persist these entries later, but must retain the
    namespace and fingerprint fields unchanged.
    """

    def __init__(self):
        self._entries = {}

    def append(self, entry):
        if not isinstance(entry, dict) or entry.get("schema") != "shared-consumer-run-ledger-entry-v1":
            raise DataArchitectureError("run ledger entry schema invalid")
        consumer = normalize_consumer(entry.get("consumer"))
        subject_id = _identity(entry.get("subject_id"), "subject id")
        if entry.get("namespace") != consumer_namespace(consumer, subject_id):
            raise DataArchitectureError("run ledger namespace mismatch")
        run_id = _identity(entry.get("run_id"), "run id")
        expected = build_run_ledger_entry(
            consumer=consumer,
            subject_id=subject_id,
            run_id=run_id,
            status=entry.get("status"),
            bundle_sha256=entry.get("bundle_sha256"),
            metadata=entry.get("metadata"),
        )
        if expected["entry_sha256"] != entry.get("entry_sha256"):
            raise DataArchitectureError("run ledger fingerprint mismatch")
        key = (consumer, subject_id, run_id)
        prior = self._entries.get(key)
        if prior is not None:
            if prior["entry_sha256"] == entry["entry_sha256"]:
                return deepcopy(prior)
            raise DataArchitectureError("run ledger duplicate conflict")
        self._entries[key] = deepcopy(entry)
        return deepcopy(entry)

    def entries(self, *, consumer=None, subject_id=None):
        if consumer is not None:
            consumer = normalize_consumer(consumer)
        rows = []
        for (row_consumer, row_subject, _), entry in self._entries.items():
            if consumer is not None and row_consumer != consumer:
                continue
            if subject_id is not None and row_subject != subject_id:
                continue
            rows.append(deepcopy(entry))
        return rows
