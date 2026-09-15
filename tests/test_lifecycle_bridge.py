from datetime import datetime, timedelta, timezone

from src.evidence_bridge import EvidencePacket
from src.lifecycle_bridge import process_evidence_packet

# Fixed safely-historical instant: lifecycle evidence intentionally rejects future evidence.
NOW = datetime(2026, 9, 14, 10, tzinfo=timezone.utc)
REC = {
    'forecast_id':'F1', 'action':'BUY_PE', 'instrument':'PE', 'strike':23500,
    'expiry':'2026-09-22', 'entry':180, 'stop':150, 'target1':250, 'target2':300,
}


def packet(**overrides):
    data=dict(forecast_id='F1', source_type='SCREENSHOT', source_ref='upload:abc',
              observed_at=NOW, captured_at=NOW+timedelta(minutes=1), instrument='PE',
              strike=23500, expiry='2026-09-22', premium=200, verified=True,
              fresh=True, contract_matched=True, continuous_path=False)
    data.update(overrides)
    return EvidencePacket(**data)


def recorder():
    calls=[]
    def run(sql, params):
        calls.append((sql,params))
        return 1
    return calls,run


def test_valid_snapshot_plans_mark_and_dry_run_does_not_write():
    calls,run=recorder()
    result=process_evidence_packet(REC,'OPEN',set(),packet(),execute_sql=run)
    assert result.actions[0].kind == 'MARK'
    assert result.execution.persisted == 0
    assert result.execution.reasons == ('WRITES_DISABLED',)
    assert calls == []


def test_valid_snapshot_terminal_threshold_cannot_false_close():
    calls,run=recorder()
    result=process_evidence_packet(REC,'OPEN',set(),packet(premium=310),execute_sql=run,writes_enabled=True)
    assert [a.kind for a in result.actions] == ['MARK']
    assert result.execution.persisted == 1
    assert calls[0][1]['event_type'] == 'MARK'


def test_stale_packet_is_no_write_even_when_writes_enabled():
    calls,run=recorder()
    result=process_evidence_packet(REC,'OPEN',set(),packet(fresh=False),execute_sql=run,writes_enabled=True)
    assert result.actions[0].kind == 'NO_WRITE'
    assert result.execution.persisted == 0
    assert calls == []


def test_forecast_mismatch_is_no_write():
    calls,run=recorder()
    result=process_evidence_packet(REC,'OPEN',set(),packet(forecast_id='F2'),execute_sql=run,writes_enabled=True)
    assert result.actions[0].payload['reason'] == 'FORECAST_ID_MISMATCH'
    assert calls == []


def test_verified_continuous_path_can_persist_terminal_events():
    calls,run=recorder()
    result=process_evidence_packet(REC,'OPEN',set(),packet(premium=310, continuous_path=True),execute_sql=run,writes_enabled=True)
    types=[params['event_type'] for _,params in calls]
    assert 'T1_HIT' in types and 'T2_HIT' in types
    assert result.execution.persisted == len(calls)
