from datetime import date

import pytest

from experiments.cache_reconcile import reconcile_candles
from experiments.data_contract import DataArchitectureError
from experiments.live_shadow_bundle import _historical_window


ROWS=[
    ["2026-09-16T03:45:00+00:00",1,2,0.5,1.5,10,0],
    ["2026-09-17T03:45:00+00:00",1.5,2.5,1,2,11,0],
]


class Client:
    def __init__(self, rows=None):
        self.rows=ROWS if rows is None else rows
        self.calls=[]
    def historical(self, key, unit, interval, start, end):
        self.calls.append((key,unit,interval,start,end))
        return {
            "payload":{"data":{"candles":self.rows}},
            "sha256":"a"*64,
            "source_path":"/v3/historical-candle/test",
            "received_at":"2026-09-18T10:00:00+00:00",
        }


class Reader:
    def __init__(self, rows=None, covers=True):
        self.rows=ROWS if rows is None else rows
        self.covers=covers
        env={"source_path":"/cached","sha256":"d"*64,"received_at":"2026-09-17T10:00:00+00:00"}
        self.records=reconcile_candles([],self.rows,env)["records"]
    def read_nifty_window(self, timeframe, start, end):
        return {
            "rows": self.rows,
            "covers_required_window": self.covers,
            "document_sha256": "b"*64,
            "dataset_sha256": "c"*64,
            "latest_cached_timestamp": "2026-09-17T03:45:00+00:00",
            "earliest_session_date": "2026-09-16",
            "latest_session_date": "2026-09-17",
            "records": self.records,
        }


def test_cache_first_complete_avoids_historical_call():
    client=Client()
    rows, provenance, audit=_historical_window(
        client,Reader(),"CACHE_FIRST","1d","days",1,date(2026,9,16),date(2026,9,17)
    )
    assert rows==ROWS
    assert client.calls==[]
    assert audit["source"]=="CACHE"
    assert audit["provider_calls_avoided"]==1
    assert provenance==["b"*64,"c"*64]


def test_shadow_exact_match_preserves_direct_primary():
    client=Client()
    rows, _, audit=_historical_window(
        client,Reader(),"SHADOW","1d","days",1,date(2026,9,16),date(2026,9,17)
    )
    assert rows==ROWS
    assert len(client.calls)==1
    assert audit["source"]=="CACHE_SHADOW"
    assert audit["shadow_exact_match"] is True


def test_shadow_mismatch_fails_closed():
    client=Client()
    bad=[list(ROWS[0]),list(ROWS[1])]
    bad[1][4]=2.4
    with pytest.raises(DataArchitectureError):
        _historical_window(
            client,Reader(rows=bad),"SHADOW","1d","days",1,date(2026,9,16),date(2026,9,17)
        )


def test_cache_first_missing_tail_uses_strict_reconciliation():
    tail=[
        ["2026-09-17T03:45:00+00:00",1.5,2.5,1,2,11,0],
        ["2026-09-18T03:45:00+00:00",2,3,1.5,2.5,12,0],
    ]
    client=Client(rows=tail)
    rows, _, audit=_historical_window(
        client,Reader(covers=False),"CACHE_FIRST","1d","days",1,date(2026,9,16),date(2026,9,18)
    )
    assert len(client.calls)==1
    assert audit["source"]=="UPSTOX_TAIL"
    assert audit["tail_calls_made"]==1
    assert audit["tail_duplicate_count"]==1
    assert audit["tail_correction_count"]==0
    assert [row[0] for row in rows]==[
        "2026-09-16T03:45:00+00:00",
        "2026-09-17T03:45:00+00:00",
        "2026-09-18T03:45:00+00:00",
    ]
