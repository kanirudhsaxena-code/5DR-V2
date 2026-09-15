from src.lifecycle_db_adapter import LifecycleDbAdapter


class Cursor:
    def __init__(self, rows=(), description=()):
        self.rows=list(rows); self.description=list(description); self.rowcount=0; self.executed=[]
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self, sql, params=()):
        self.executed.append((sql,params)); self.rowcount=1
    def fetchall(self): return self.rows

class Conn:
    def __init__(self, cursor): self._cursor=cursor; self.commits=0; self.rollbacks=0; self.closed=False
    def cursor(self): return self._cursor
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): self.closed=True


def test_writes_disabled_is_noop():
    cur=Cursor(); conn=Conn(cur); db=LifecycleDbAdapter(lambda: conn)
    assert db.execute_lifecycle_sql('INSERT INTO recommendation_events VALUES (1)', {}, writes_enabled=False) == 0
    assert cur.executed == [] and conn.commits == 0


def test_rejects_non_allowlisted_write():
    cur=Cursor(); conn=Conn(cur); db=LifecycleDbAdapter(lambda: conn)
    try:
        db.execute_lifecycle_sql('DELETE FROM recommendation_events', {}, writes_enabled=True)
        assert False
    except ValueError:
        pass
    assert cur.executed == []


def test_allowlisted_insert_commits():
    cur=Cursor(); conn=Conn(cur); db=LifecycleDbAdapter(lambda: conn)
    assert db.execute_lifecycle_sql('INSERT INTO recommendation_events(forecast_id) VALUES (%(forecast_id)s)', {'forecast_id':'F1'}, writes_enabled=True) == 1
    assert conn.commits == 1


def test_existing_event_types_parameterized():
    cur=Cursor(rows=[('ISSUED',),('ENTRY_REFERENCE_SET',)], description=[('event_type',)])
    conn=Conn(cur); db=LifecycleDbAdapter(lambda: conn)
    assert db.existing_event_types('F1') == {'ISSUED','ENTRY_REFERENCE_SET'}
    assert cur.executed[0][1] == ('F1',)
