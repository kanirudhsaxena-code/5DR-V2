import json
from datetime import datetime, timezone
from src.production_lifecycle_runner import RunItem, RunSummary
from src.run_audit import audit_dict, write_audit

NOW=datetime(2026,9,15,10,tzinfo=timezone.utc)

def summary():
 return RunSummary(NOW,NOW,False,1,0,1,0,1,1,(RunItem('F1','OPEN',('NO_WRITE',),0,('NO_EVIDENCE_PACKET',)),))

def test_audit_is_json_safe_and_explicit():
 data=audit_dict(summary())
 assert data['writes_enabled'] is False
 assert data['items'][0]['reasons']==('NO_EVIDENCE_PACKET',)
 assert data['started_at'].endswith('+00:00')

def test_write_audit_round_trips(tmp_path):
 p=write_audit(summary(),tmp_path/'audit.json')
 data=json.loads(p.read_text())
 assert data['persisted']==0 and data['missing_evidence']==1
