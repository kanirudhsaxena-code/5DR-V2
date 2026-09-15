from pathlib import Path

from src.production_activation import activate


class Db:
    def __init__(self): self.reads=0; self.writes=0
    def actionable_recommendations(self): self.reads += 1; return []
    def existing_event_types(self, forecast_id): return set()
    def execute_lifecycle_sql(self, sql, params, *, writes_enabled=False):
        if writes_enabled: self.writes += 1
        return 0


def test_no_evidence_is_no_write(tmp_path):
    db=Db()
    result=activate(db, tmp_path/'missing.json', writes_enabled=True)
    assert result.mode == 'NO_WRITE'
    assert result.reason == 'NO_EVIDENCE_HANDOFF'
    assert db.reads == 0 and db.writes == 0


def test_valid_empty_handoff_dry_run(tmp_path):
    p=tmp_path/'evidence.json'; p.write_text('[]', encoding='utf-8')
    db=Db(); result=activate(db, p)
    assert result.mode == 'DRY_RUN'
    assert result.summary is not None
    assert result.summary.writes_enabled is False
    assert db.writes == 0


def test_valid_empty_handoff_write_mode_has_no_fabricated_write(tmp_path):
    p=tmp_path/'evidence.json'; p.write_text('[]', encoding='utf-8')
    db=Db(); result=activate(db, p, writes_enabled=True)
    assert result.mode == 'WRITE_ENABLED'
    assert result.summary.persisted == 0
    assert db.writes == 0
