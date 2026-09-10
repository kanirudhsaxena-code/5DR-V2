from datetime import datetime
from zoneinfo import ZoneInfo

from src.governance import (
    Candidate, classify_run, latest_valid_candidate,
    stability_score, revision_brier_improvement, d1_policy
)

IST = ZoneInfo("Asia/Kolkata")

def test_classification():
    assert classify_run(datetime(2026,9,10,15,20,tzinfo=IST)) == "CANONICAL_CANDIDATE"
    assert classify_run(datetime(2026,9,11,9,14,59,tzinfo=IST)) == "CANONICAL_CANDIDATE"
    assert classify_run(datetime(2026,9,11,9,15,tzinfo=IST)) == "INTRADAY_SNAPSHOT"
    assert classify_run(datetime(2026,9,11,12,0,tzinfo=IST)) == "INTRADAY_SNAPSHOT"

def test_latest_valid_candidate_ignores_later_invalid():
    c1 = Candidate("a", datetime(2026,9,10,15,25,tzinfo=IST), True)
    c2 = Candidate("b", datetime(2026,9,11,8,45,tzinfo=IST), True)
    c3 = Candidate("c", datetime(2026,9,11,9,5,tzinfo=IST), False)
    assert latest_valid_candidate([c1,c2,c3]).forecast_id == "b"

def test_stability_and_revision():
    assert stability_score(0) == 100
    assert stability_score(1) == 75
    assert stability_score(4) == 0
    assert revision_brier_improvement(0.42, 0.31) == 0.11

def test_d1_policy():
    assert d1_policy("CANONICAL_CANDIDATE") == "TARGET_TRADING_DATE"
    assert d1_policy("INTRADAY_SNAPSHOT") == "NEXT_FULL_TRADING_SESSION"
