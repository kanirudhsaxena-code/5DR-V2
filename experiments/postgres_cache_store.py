"""PostgreSQL/Neon-capable durable MarketCacheStore implementation.

This file contains storage mechanics only. It has no credentials, network bootstrap,
Upstox dependency, canonical 5DR table knowledge, forecast code, or trading surface.
A caller must inject a small transactional database boundary. The backend is marked
production-approved only when the caller explicitly supplies that state after the
separate deployment approval gate.
"""
import json
import re

from experiments.cache_store import MarketCacheStore, validate_cache_document
from experiments.data_contract import DataArchitectureError

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class PostgresMarketCacheStore(MarketCacheStore):
    backend_id = "POSTGRES_JSONB_MARKET_CACHE_V1"

    def __init__(self, database, *, schema="market_data_cache", production_approved=False):
        if database is None:
            raise DataArchitectureError("database boundary missing")
        if not isinstance(schema, str) or not IDENTIFIER_RE.fullmatch(schema):
            raise DataArchitectureError("cache schema identifier invalid")
        if not isinstance(production_approved, bool):
            raise DataArchitectureError("production approval state invalid")
        for method in ("fetch_one", "fetch_all", "execute"):
            if not callable(getattr(database, method, None)):
                raise DataArchitectureError("database boundary incomplete")
        self.database = database
        self.schema = schema
        self.production_approved = production_approved
        self.table = f'{schema}.market_cache_documents'

    @staticmethod
    def migration_sql(schema="market_data_cache"):
        if not isinstance(schema, str) or not IDENTIFIER_RE.fullmatch(schema):
            raise DataArchitectureError("cache schema identifier invalid")
        table = f'{schema}.market_cache_documents'
        return (
            f'CREATE SCHEMA IF NOT EXISTS {schema};\n'
            f'CREATE TABLE IF NOT EXISTS {table} (\n'
            '  series_id text PRIMARY KEY,\n'
            '  provider_id text NOT NULL,\n'
            '  source_semantic text NOT NULL,\n'
            '  document_sha256 char(64) NOT NULL,\n'
            '  dataset_sha256 char(64) NOT NULL,\n'
            '  latest_timestamp timestamptz NULL,\n'
            '  record_count integer NOT NULL CHECK (record_count >= 0),\n'
            '  document jsonb NOT NULL,\n'
            '  updated_at timestamptz NOT NULL DEFAULT now(),\n'
            "  CHECK (document->>'schema' = 'market-cache-document-v1'),\n"
            "  CHECK (document->>'series_id' = series_id),\n"
            "  CHECK (document->>'document_sha256' = document_sha256),\n"
            "  CHECK (document->>'dataset_sha256' = dataset_sha256)\n"
            ');\n'
            f'CREATE INDEX IF NOT EXISTS market_cache_documents_updated_at_idx '
            f'ON {table} (updated_at);'
        )

    @staticmethod
    def _series_id(series_id):
        if not isinstance(series_id, str) or not series_id.strip() or len(series_id) > 200:
            raise DataArchitectureError("cache series id invalid")
        return series_id.strip()

    @staticmethod
    def _decode_document(value):
        if isinstance(value, dict):
            document = value
        elif isinstance(value, str):
            try:
                document = json.loads(value)
            except json.JSONDecodeError:
                raise DataArchitectureError("stored cache document is not valid JSON") from None
        else:
            raise DataArchitectureError("stored cache document type invalid")
        validate_cache_document(document)
        return document

    def read_document(self, series_id):
        series_id = self._series_id(series_id)
        row = self.database.fetch_one(
            f'SELECT document FROM {self.table} WHERE series_id = %s',
            (series_id,),
        )
        if row is None:
            return None
        if not isinstance(row, (tuple, list)) or len(row) != 1:
            raise DataArchitectureError("cache database read shape invalid")
        document = self._decode_document(row[0])
        if document["series_id"] != series_id:
            raise DataArchitectureError("cache database series identity mismatch")
        return document

    def write_document(self, document, *, expected_document_sha256=None):
        summary = validate_cache_document(document)
        if expected_document_sha256 is not None:
            if (not isinstance(expected_document_sha256, str) or
                    len(expected_document_sha256) != 64 or
                    any(char not in "0123456789abcdef" for char in expected_document_sha256.lower())):
                raise DataArchitectureError("expected cache document fingerprint invalid")
            expected_document_sha256 = expected_document_sha256.lower()

        payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        params = (
            document["series_id"], document["provider_id"], document["source_semantic"],
            document["document_sha256"], document["dataset_sha256"],
            document["latest_timestamp"], document["record_count"], payload,
        )
        if expected_document_sha256 is None:
            row = self.database.fetch_one(
                f'INSERT INTO {self.table} '
                '(series_id, provider_id, source_semantic, document_sha256, dataset_sha256, '
                'latest_timestamp, record_count, document) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) '
                'ON CONFLICT (series_id) DO NOTHING RETURNING document_sha256',
                params,
            )
            if row is None:
                raise DataArchitectureError("cache create conflict; compare-and-swap required")
        else:
            row = self.database.fetch_one(
                f'UPDATE {self.table} SET provider_id=%s, source_semantic=%s, '
                'document_sha256=%s, dataset_sha256=%s, latest_timestamp=%s, '
                'record_count=%s, document=%s::jsonb, updated_at=now() '
                'WHERE series_id=%s AND document_sha256=%s RETURNING document_sha256',
                (
                    document["provider_id"], document["source_semantic"],
                    document["document_sha256"], document["dataset_sha256"],
                    document["latest_timestamp"], document["record_count"], payload,
                    document["series_id"], expected_document_sha256,
                ),
            )
            if row is None:
                raise DataArchitectureError("cache compare-and-swap conflict")

        stored = self.read_document(document["series_id"])
        if stored is None or stored["document_sha256"] != document["document_sha256"]:
            raise DataArchitectureError("cache durable readback verification failed")
        return validate_cache_document(stored)

    def list_series(self):
        rows = self.database.fetch_all(
            f'SELECT series_id FROM {self.table} ORDER BY series_id',
            (),
        )
        if not isinstance(rows, list):
            raise DataArchitectureError("cache database list shape invalid")
        series = []
        for row in rows:
            if not isinstance(row, (tuple, list)) or len(row) != 1:
                raise DataArchitectureError("cache database list row invalid")
            series.append(self._series_id(row[0]))
        if len(series) != len(set(series)):
            raise DataArchitectureError("cache database duplicate series")
        return series

    def recover(self):
        row = self.database.fetch_one('SELECT 1', ())
        if row not in ((1,), [1]):
            raise DataArchitectureError("cache database health check failed")
        return {"status": "POSTGRES_CACHE_HEALTHY", "recovered": 0}

    def describe(self):
        return {
            "backend_id": self.backend_id,
            "provider_neutral": True,
            "production_approved": self.production_approved,
            "canonical_5dr_storage": False,
            "durable": True,
            "transactional": True,
            "compare_and_swap": True,
            "schema": self.schema,
            "credential_embedded": False,
        }
