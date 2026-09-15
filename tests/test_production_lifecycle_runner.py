from datetime import datetime, timedelta, timezone

from src.evidence_bridge import EvidencePacket
from src.production_lifecycle_runner import run_lifecycle

NOW=datetime(2026,9,15,10,tzinfo=timezone.utc)
ROW={
 'forecast_id':'F1','recommendation':'BUY_PE','instrument':'PE','strike':'23500',
 'expiry':'2026-09-22T00:00:00Z','observed_premium':'180','stop_premium':'150',
 'target1_premium':'250','target2_premium':'300','lifecycle_status':'OPEN'
}

def packet(fid='F1', premium=200, continuous=False):
 return EvidencePacket(forecast_id=fid,source_type='SCREENSHOT',source_ref='upload:x',
  observed_at=NOW-timedelta(hours=2),captured_at=NOW-timedelta(hours=1),instrument='PE',
  strike=23500,expiry='2026-09-22',premium=premium,verified=True,fresh=True,
  contract_matched=True,continuous_path=continuous)

def events(_): return set()

def test_missing_evidence_is_explicit_no_write():
 calls=[]
 summary=run_lifecycle([ROW],[],events,execute_sql=lambda s,p:calls.append((s,p)) or 1,now=lambda:NOW)
 assert summary.missing_evidence==1 and summary.persisted==0 and calls==[]
 assert summary.items[0].reasons==('NO_EVIDENCE_PACKET',)

def test_duplicate_packets_fail_closed():
 calls=[]
 summary=run_lifecycle([ROW],[packet(),packet()],events,execute_sql=lambda s,p:calls.append((s,p)) or 1,writes_enabled=True,now=lambda:NOW)
 assert summary.persisted==0 and summary.no_write==1 and calls==[]
 assert summary.items[0].reasons==('DUPLICATE_EVIDENCE_PACKET',)

def test_dry_run_never_writes():
 calls=[]
 summary=run_lifecycle([ROW],[packet()],events,execute_sql=lambda s,p:calls.append((s,p)) or 1,now=lambda:NOW)
 assert summary.persisted==0 and calls==[] and summary.writes_enabled is False

def test_enabled_snapshot_persists_mark_only():
 calls=[]
 summary=run_lifecycle([ROW],[packet(premium=310)],events,execute_sql=lambda s,p:calls.append((s,p)) or 1,writes_enabled=True,now=lambda:NOW)
 assert summary.persisted==1
 assert calls[0][1]['event_type']=='MARK'

def test_enabled_continuous_path_can_persist_targets():
 calls=[]
 summary=run_lifecycle([ROW],[packet(premium=310,continuous=True)],events,execute_sql=lambda s,p:calls.append((s,p)) or 1,writes_enabled=True,now=lambda:NOW)
 types=[p['event_type'] for _,p in calls]
 assert types==['T1_HIT','T2_HIT']
 assert summary.persisted==2
