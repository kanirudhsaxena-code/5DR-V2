import json
from pathlib import Path
import pytest
from src.evidence_handoff import load_packets, packet_from_dict


def valid():
    return {'forecast_id':'F1','source_type':'SCREENSHOT','source_ref':'shot-1','observed_at':'2026-09-15T16:43:00+05:30','captured_at':'2026-09-15T16:44:00+05:30','instrument':'PE','strike':23200,'expiry':'2026-09-22','premium':172.7,'verified':True,'fresh':True,'contract_matched':True,'continuous_path':False}


def test_valid_packet_loads_and_stays_snapshot():
    p=packet_from_dict(valid())
    assert p.forecast_id=='F1' and p.continuous_path is False


def test_naive_timestamp_rejected():
    raw=valid(); raw['observed_at']='2026-09-15T16:43:00'
    with pytest.raises(ValueError): packet_from_dict(raw)


def test_unverified_rejected_fail_closed():
    raw=valid(); raw['verified']=False
    with pytest.raises(ValueError): packet_from_dict(raw)


def test_duplicate_forecast_rejected(tmp_path: Path):
    path=tmp_path/'evidence.json'; path.write_text(json.dumps([valid(),valid()]), encoding='utf-8')
    with pytest.raises(ValueError): load_packets(path)


def test_unknown_field_rejected():
    raw=valid(); raw['surprise']='x'
    with pytest.raises(ValueError): packet_from_dict(raw)
