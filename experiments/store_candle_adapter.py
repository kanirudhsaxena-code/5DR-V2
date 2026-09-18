"""Bridge the historical backfill executor to the hardened MarketCacheStore contract.

The executor intentionally knows only a narrow ``write_candles`` surface.  This adapter
is the only supported bridge from that surface into durable cache documents: it reads
and validates the current document, reconciles overlaps/corrections, rebuilds the
signed document, and writes it with compare-and-swap semantics.

No database, lifecycle, forecast, trading, or provider client is imported here.
"""
from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import (
    MarketCacheStore,
    build_cache_document,
    validate_cache_document,
)
from experiments.data_contract import DataArchitectureError


class StoreBackedCandleCache:
    """Candle-write facade backed by a provider-neutral MarketCacheStore."""

    def __init__(self, store, *, provider_id="UPSTOX",
                 source_semantic="UPSTOX_AUTHENTICATED",
                 require_production_approved=False):
        if not isinstance(store, MarketCacheStore):
            raise DataArchitectureError("market cache store contract required")
        if not isinstance(require_production_approved, bool):
            raise DataArchitectureError("production approval gate invalid")
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise DataArchitectureError("cache provider id invalid")
        if not isinstance(source_semantic, str) or not source_semantic.strip():
            raise DataArchitectureError("cache source semantic invalid")

        descriptor = store.describe()
        if not isinstance(descriptor, dict) or descriptor.get("provider_neutral") is not True:
            raise DataArchitectureError("cache store is not provider-neutral")
        # Durable market history must remain physically/logically separate from the
        # canonical forecast/lifecycle store.  Every concrete backend must declare it.
        if descriptor.get("canonical_5dr_storage") is not False:
            raise DataArchitectureError("cache store isolation not proven")
        if require_production_approved and descriptor.get("production_approved") is not True:
            raise DataArchitectureError("cache store is not production approved")

        self.store = store
        self.provider_id = provider_id.strip()
        self.source_semantic = source_semantic.strip()
        self.require_production_approved = require_production_approved

    def _existing(self, series_id):
        current = self.store.read_document(series_id)
        if current is None:
            return None
        validate_cache_document(current)
        if current["series_id"] != series_id.strip():
            raise DataArchitectureError("cache series identity mismatch")
        if current["provider_id"] != self.provider_id:
            raise DataArchitectureError("cache provider identity mismatch")
        if current["source_semantic"] != self.source_semantic:
            raise DataArchitectureError("cache source semantic mismatch")
        return current

    def write_candles(self, series_id, candles, envelope, *, retention_cutoff=None):
        if not isinstance(series_id, str) or not series_id.strip():
            raise DataArchitectureError("cache series id invalid")
        if not isinstance(candles, list):
            raise DataArchitectureError("cache candle batch invalid")

        current = self._existing(series_id)
        existing_records = [] if current is None else current["records"]
        prior_audit = () if current is None else current["audit_events"]
        expected = None if current is None else current["document_sha256"]

        reconciliation = reconcile_candles(
            existing_records,
            candles,
            envelope,
            retention_cutoff=retention_cutoff,
        )
        document = build_cache_document(
            series_id.strip(),
            reconciliation,
            provider_id=self.provider_id,
            source_semantic=self.source_semantic,
            prior_audit_events=prior_audit,
        )
        if expected is None:
            written = self.store.write_document(document)
        else:
            written = self.store.write_document(
                document, expected_document_sha256=expected,
            )
        return {
            "status": "STORE_BACKED_CANDLE_WRITE_PASSED",
            "series_id": series_id.strip(),
            "record_count": written["record_count"],
            "latest_timestamp": written["latest_timestamp"],
            "dataset_sha256": written["dataset_sha256"],
            "document_sha256": written["document_sha256"],
            "duplicate_count": reconciliation["duplicate_count"],
            "correction_count": reconciliation["correction_count"],
            "pruned_count": reconciliation["pruned_count"],
            "audit_event_count": written["audit_event_count"],
        }

    def latest_timestamp(self, series_id):
        current = self._existing(series_id)
        return None if current is None else current["latest_timestamp"]

    def describe(self):
        descriptor = dict(self.store.describe())
        descriptor.update({
            "adapter": "STORE_BACKED_CANDLE_CACHE_V1",
            "provider_id": self.provider_id,
            "source_semantic": self.source_semantic,
            "require_production_approved": self.require_production_approved,
        })
        return descriptor
