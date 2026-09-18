"""Atomic JSON reference implementation of MarketCacheStore for tests only.

This backend is intentionally hard-locked to `test_mode=True`. It is not an approved
persistent backend for 5DR and must never be used as production/canonical storage.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from experiments.cache_store import MarketCacheStore, validate_cache_document
from experiments.data_contract import DataArchitectureError


class JsonFileReferenceCacheStore(MarketCacheStore):
    backend_id = "JSON_FILE_REFERENCE_TEST_ONLY"
    _TEMP_PREFIX = ".market-cache-"
    _TEMP_SUFFIX = ".tmp"

    def __init__(self, root, *, test_mode=False):
        if test_mode is not True:
            raise DataArchitectureError("reference cache backend is test-mode only")
        if not isinstance(root, (str, os.PathLike)) or not str(root):
            raise DataArchitectureError("reference cache root invalid")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise DataArchitectureError("reference cache root unavailable")

    @staticmethod
    def _series_filename(series_id):
        if not isinstance(series_id, str) or not series_id.strip():
            raise DataArchitectureError("reference cache series id invalid")
        return hashlib.sha256(series_id.strip().encode()).hexdigest() + ".json"

    def _path(self, series_id):
        return self.root / self._series_filename(series_id)

    def _load_path(self, path):
        try:
            raw = path.read_text(encoding="utf-8")
            document = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise DataArchitectureError("reference cache document unreadable") from None
        validate_cache_document(document)
        return document

    def read_document(self, series_id):
        path = self._path(series_id)
        if not path.exists():
            return None
        document = self._load_path(path)
        if document["series_id"] != series_id.strip():
            raise DataArchitectureError("reference cache series identity mismatch")
        return document

    def write_document(self, document, *, expected_document_sha256=None):
        validated = validate_cache_document(document)
        if expected_document_sha256 is not None:
            if not isinstance(expected_document_sha256, str) or len(expected_document_sha256) != 64:
                raise DataArchitectureError("reference cache expected fingerprint invalid")
        path = self._path(document["series_id"])
        existing = self.read_document(document["series_id"])
        if existing is None:
            if expected_document_sha256 is not None:
                raise DataArchitectureError("reference cache compare-and-swap missing document")
        else:
            if expected_document_sha256 is None:
                raise DataArchitectureError("reference cache overwrite requires expected fingerprint")
            if existing["document_sha256"] != expected_document_sha256:
                raise DataArchitectureError("reference cache compare-and-swap mismatch")

        handle = None
        temp_path = None
        try:
            handle = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.root,
                prefix=self._TEMP_PREFIX, suffix=self._TEMP_SUFFIX, delete=False,
            )
            temp_path = Path(handle.name)
            json.dump(document, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            handle = None
            os.replace(temp_path, path)
        except OSError:
            raise DataArchitectureError("reference cache atomic write failed") from None
        finally:
            if handle is not None:
                handle.close()
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
        stored = self.read_document(document["series_id"])
        if stored is None or stored["document_sha256"] != validated["document_sha256"]:
            raise DataArchitectureError("reference cache post-write verification failed")
        return validated

    def list_series(self):
        series = []
        seen = set()
        try:
            paths = sorted(self.root.glob("*.json"))
        except OSError:
            raise DataArchitectureError("reference cache listing failed") from None
        for path in paths:
            document = self._load_path(path)
            expected_name = self._series_filename(document["series_id"])
            if path.name != expected_name:
                raise DataArchitectureError("reference cache filename identity mismatch")
            if document["series_id"] in seen:
                raise DataArchitectureError("reference cache duplicate series")
            seen.add(document["series_id"])
            series.append(document["series_id"])
        return series

    def recover(self):
        removed = 0
        for path in self.root.glob(self._TEMP_PREFIX + "*" + self._TEMP_SUFFIX):
            try:
                path.unlink()
                removed += 1
            except OSError:
                raise DataArchitectureError("reference cache temp recovery failed") from None
        return {"status": "REFERENCE_CACHE_RECOVERY_PASS", "stale_temp_files_removed": removed}

    def describe(self):
        return {
            **super().describe(),
            "test_mode_only": True,
            "production_approved": False,
            "canonical_5dr_storage": False,
        }
