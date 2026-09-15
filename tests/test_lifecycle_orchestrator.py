from datetime import date, datetime, timezone
from src.lifecycle_evidence import OptionEvidence
from src.lifecycle_orchestrator import plan_recommendation, plan_due_checkpoints, efficacy_ready

REC={'action':'BUY_PE','instrument':'PE','strike':23500,'expiry':'2026-09-22','entry':180,'stop':150,'target1':250,'target2':295}

def ev(premium, continuous=False):
    return OptionEvidence('PE',23500,'2026-09-22',premium,datetime(2026,9,15,4,tzinfo=timezone.utc),'verified',continuous)

def test_missing_evidence_is_no_write():
    a=plan_recommendation(REC,'OPEN',None,set())
    assert a[0].kind=='NO_WRITE'

def test_ambiguous_terminal_snapshot_degrades_to_mark():
    a=plan_recommendation(REC,'OPEN',ev(310),set())
    assert [x.kind for x in a]==['MARK']

def test_continuous_path_can_emit_targets():
    a=plan_recommendation(REC,'OPEN',ev(310,True),set())
    assert [x.payload['event_type'] for x in a]==['T1_HIT','T2_HIT']

def test_due_checkpoint_fails_closed_without_verified_market_evidence():
    cps=[{'checkpoint_id':1,'due_date':date(2026,9,15),'status':'DUE'}]
    assert plan_due_checkpoints(cps,date(2026,9,15),None)[0].kind=='NO_WRITE'

def test_verified_checkpoint_is_planned():
    cps=[{'checkpoint_id':1,'due_date':date(2026,9,15),'status':'DUE'}]
    a=plan_due_checkpoints(cps,date(2026,9,15),{'verified':True,'actual_nifty':23350})
    assert a[0].kind=='CHECKPOINT'

def test_efficacy_only_after_closed_scorable_path_and_checkpoint():
    assert efficacy_ready('CLOSED_T2','WIN',1)
    assert not efficacy_ready('OPEN',None,3)
    assert not efficacy_ready('CLOSED_T2','WIN',0)
