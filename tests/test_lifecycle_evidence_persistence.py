from datetime import datetime, timezone
import pytest
from src.lifecycle_evidence import OptionEvidence, path_can_close
from src.lifecycle_persistence import recommendation_event_insert, assert_append_only_event_sql


def evidence(**overrides):
    data=dict(instrument='PE',strike=23500,expiry='2026-09-22',premium=200,
              observed_at=datetime(2026,9,15,4,0,tzinfo=timezone.utc),source_ref='verified-feed')
    data.update(overrides)
    return OptionEvidence(**data)


def test_matching_contract_accepted():
    evidence().validate_for(instrument='PE',strike=23500,expiry='2026-09-22')


def test_wrong_expiry_rejected():
    with pytest.raises(ValueError, match='expiry mismatch'):
        evidence().validate_for(instrument='PE',strike=23500,expiry='2026-09-29')


def test_snapshot_cannot_close_ordered_path():
    assert not path_can_close(evidence())
    assert path_can_close(evidence(continuous_path=True))


def test_autonomous_event_allowlist():
    assert 'INSERT INTO recommendation_events' in recommendation_event_insert('MARK')
    with pytest.raises(ValueError):
        recommendation_event_insert('ENTRY_TRIGGERED')


def test_append_only_guard():
    assert_append_only_event_sql(recommendation_event_insert('T1_HIT'))
    with pytest.raises(ValueError):
        assert_append_only_event_sql('DELETE FROM recommendation_events')
