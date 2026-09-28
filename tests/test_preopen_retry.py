from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from experiments.data_contract import DataArchitectureError
from experiments.preopen_retry import latest_intraday_with_retry

IST = ZoneInfo("Asia/Kolkata")


class FakeClient:
    def __init__(self, responses):
        self.responses=list(responses)
        self.calls=0

    def intraday(self, instrument_key, unit, interval):
        self.calls += 1
        return self.responses.pop(0)


def env(candles):
    return {"payload":{"data":{"candles":candles}},"sha256":"abc","source_path":"fake"}


def test_empty_first_response_retries_then_accepts_valid_preopen_candle():
    row=["2026-09-28T09:10:30+05:30",100,101,99,100.5,1234,0]
    client=FakeClient([env([]),env([row])])
    sleeps=[]
    result_env,latest=latest_intraday_with_retry(
        client,"KEY",attempts=3,sleep_seconds=0,
        clock=lambda: datetime(2026,9,28,9,10,30,tzinfo=IST),
        sleeper=lambda seconds: sleeps.append(seconds),
    )
    assert latest==row
    assert result_env["payload"]["data"]["candles"]==[row]
    assert client.calls==2
    assert len(sleeps)==1


def test_all_empty_responses_fail_closed_without_stale_substitution():
    client=FakeClient([env([]),env([]),env([])])
    with pytest.raises(DataArchitectureError,match="failed closed after bounded retries"):
        latest_intraday_with_retry(
            client,"KEY",attempts=3,sleep_seconds=0,
            clock=lambda: datetime(2026,9,28,9,11,tzinfo=IST),
            sleeper=lambda seconds: None,
        )
    assert client.calls==3


def test_retry_stops_at_0915_normal_market_boundary():
    client=FakeClient([env([]),env([["2026-09-28T09:14:00+05:30",1,1,1,1,1,1]])])
    times=iter([
        datetime(2026,9,28,9,15,tzinfo=IST),
    ])
    with pytest.raises(DataArchitectureError,match="failed closed after bounded retries"):
        latest_intraday_with_retry(
            client,"KEY",attempts=3,sleep_seconds=0,
            clock=lambda: next(times),
            sleeper=lambda seconds: None,
        )
    assert client.calls==1


def test_malformed_candle_rows_are_not_accepted():
    client=FakeClient([env([["2026-09-28T09:11:00+05:30",1,2]])])
    with pytest.raises(DataArchitectureError,match="malformed intraday candle row"):
        latest_intraday_with_retry(
            client,"KEY",attempts=1,
            clock=lambda: datetime(2026,9,28,9,11,tzinfo=IST),
            sleeper=lambda seconds: None,
        )
