from datetime import date

from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import build_cache_document
from experiments.postgres_cache_store import PostgresMarketCacheStore
from experiments.production_cache_read import ProductionHistoricalCacheReader


class Db:
    def __init__(self, document):
        self.document=document
    def fetch_one(self, sql, params=()):
        if sql == "SELECT 1": return (1,)
        return (self.document,)
    def fetch_all(self, sql, params=()): return []
    def execute(self, sql, params=()): raise AssertionError("writes forbidden")


def _doc():
    env={"source_path":"/test","sha256":"a"*64,"received_at":"2026-09-18T00:00:00+00:00"}
    rows=[
      ["2026-09-16T03:45:00+00:00",1,2,0.5,1.5,10,0],
      ["2026-09-17T03:45:00+00:00",1.5,2.5,1,2,11,0],
    ]
    rec=reconcile_candles([], rows, env)
    return build_cache_document("5DR:NIFTY_PRICE_CANDLES:NIFTY_50:1d",rec,provider_id="UPSTOX",source_semantic="UPSTOX_AUTHENTICATED")


def test_validated_cache_window_hit():
    reader=ProductionHistoricalCacheReader(PostgresMarketCacheStore(Db(_doc()),production_approved=True))
    result=reader.read_nifty_window("1d",date(2026,9,16),date(2026,9,17))
    assert result["status"]=="HIT"
    assert result["covers_required_window"] is True
    assert len(result["rows"])==2
    assert result["document_sha256"]==_doc()["document_sha256"]


def test_partial_window_is_explicit():
    reader=ProductionHistoricalCacheReader(PostgresMarketCacheStore(Db(_doc()),production_approved=True))
    result=reader.read_nifty_window("1d",date(2026,9,15),date(2026,9,17))
    assert result["status"]=="PARTIAL"
    assert result["covers_required_window"] is False
