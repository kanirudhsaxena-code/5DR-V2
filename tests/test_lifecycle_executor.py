from datetime import datetime, timezone
import pytest
from src.lifecycle_executor import execute_actions
from src.lifecycle_orchestrator import ProposedAction

NOW=datetime(2026,9,15,9,tzinfo=timezone.utc)


def recorder():
    calls=[]
    def run(sql, params):
        calls.append((sql,params))
        return 1
    return calls,run


def test_writes_disabled_is_hard_dry_run():
    calls,run=recorder()
    actions=[ProposedAction('MARK',{'premium':180,'source_ref':'verified','observed_at':NOW})]
    result=execute_actions('F1',actions,execute_sql=run,writes_enabled=False)
    assert not calls
    assert result.persisted==0 and result.reasons==('WRITES_DISABLED',)


def test_no_write_never_executes_even_when_enabled():
    calls,run=recorder()
    result=execute_actions('F1',[ProposedAction('NO_WRITE',{'reason':'STALE'})],execute_sql=run,writes_enabled=True)
    assert not calls and result.persisted==0 and result.reasons==('STALE',)


def test_mark_translates_to_guarded_event_insert():
    calls,run=recorder()
    action=ProposedAction('MARK',{'premium':180,'source_ref':'verified','observed_at':NOW,'note':'safe mark'})
    result=execute_actions('F1',[action],execute_sql=run,writes_enabled=True)
    assert result.persisted==1
    sql,params=calls[0]
    assert 'INSERT INTO recommendation_events' in sql
    assert 'WHERE NOT EXISTS' in sql
    assert params['event_type']=='MARK' and params['forecast_id']=='F1'


def test_event_preserves_calculated_metrics():
    calls,run=recorder()
    action=ProposedAction('EVENT',{'event_type':'T1_HIT','premium':250,'pnl_pct':40,'r_multiple':2,'source_ref':'verified','observed_at':NOW})
    execute_actions('F1',[action],execute_sql=run,writes_enabled=True)
    _,params=calls[0]
    assert params['event_type']=='T1_HIT' and params['pnl_pct']==40 and params['r_multiple']==2


def test_checkpoint_is_due_only_update_contract():
    calls,run=recorder()
    action=ProposedAction('CHECKPOINT',{'checkpoint_id':37,'observed_at':NOW,'actual_nifty':23350,'source_ref':'verified'})
    execute_actions('F1',[action],execute_sql=run,writes_enabled=True)
    sql,params=calls[0]
    assert "WHERE checkpoint_id=%(checkpoint_id)s AND status='DUE'" in sql
    assert params['checkpoint_id']==37


def test_unknown_action_fails_closed():
    calls,run=recorder()
    with pytest.raises(ValueError):
        execute_actions('F1',[ProposedAction('DELETE',{})],execute_sql=run,writes_enabled=True)
    assert not calls
