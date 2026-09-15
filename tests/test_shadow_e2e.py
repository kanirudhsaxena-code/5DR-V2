import json
from datetime import datetime, timedelta, timezone

from src.autonomous_acquisition import SourceObservation
from src.shadow_e2e import run_shadow

NOW = datetime(2026, 9, 15, 16, 20, tzinfo=timezone.utc)


class FakeDb:
    def __init__(self):
        self.execute_calls = []

    def actionable_recommendations(self):
        return []

    def existing_event_types(self, forecast_id):
        return set()

    def execute_lifecycle_sql(self, sql, params, *, writes_enabled=False):
        self.execute_calls.append((sql, params, writes_enabled))
        if writes_enabled:
            raise AssertionError('shadow attempted a write')
        return False


def observations(status='VERIFIED'):
    stamp = (NOW - timedelta(minutes=1)).isoformat()
    return [
        SourceObservation('MARKET_TRUST', 'market-source', stamp, status=status, detail='ok'),
        SourceObservation('EVENT_SHOCK', 'event-source', stamp, status=status, detail='ok'),
        SourceObservation('EXECUTION_RISK', 'execution-source', stamp, status=status, detail='ok'),
    ]


def packet_file(tmp_path):
    path = tmp_path / 'evidence.json'
    path.write_text(json.dumps([{
        'forecast_id': 'F-SHADOW-1',
        'source_type': 'SCREENSHOT',
        'source_ref': 'verified-shadow-screenshot',
        'observed_at': (NOW - timedelta(minutes=2)).isoformat(),
        'captured_at': (NOW - timedelta(minutes=1)).isoformat(),
        'instrument': 'PE',
        'strike': 23200,
        'expiry': '2026-09-22',
        'premium': 172.7,
        'verified': True,
        'fresh': True,
        'contract_matched': True,
        'continuous_path': False,
    }]))
    return path


def test_ready_chain_reaches_dry_run_and_never_writes(tmp_path):
    db = FakeDb()
    result = run_shadow(db, packet_file(tmp_path), observations(), request_id='shadow-1', now=NOW)
    assert result.acquisition_status == 'AUTONOMOUS_EVIDENCE_READY'
    assert result.gate_status == 'CANONICAL_EVIDENCE_READY'
    assert result.activation.mode == 'DRY_RUN'
    assert result.activation.writes_enabled is False
    assert db.execute_calls == []


def test_incomplete_acquisition_blocks_before_lifecycle(tmp_path):
    db = FakeDb()
    incomplete = observations()[:2]
    result = run_shadow(db, packet_file(tmp_path), incomplete, request_id='shadow-2', now=NOW)
    assert result.acquisition_status == 'AUTONOMOUS_EVIDENCE_BLOCKED'
    assert result.activation is None
    assert db.execute_calls == []
