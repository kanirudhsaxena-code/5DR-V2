from src.lifecycle_persistence import recommendation_event_insert


class InMemoryEventDb:
    """Tiny persistence simulator for the exact NOT EXISTS identity used by production SQL."""

    def __init__(self):
        self.rows = []

    def execute(self, sql, params):
        assert "INSERT INTO recommendation_events" in sql
        identity = (
            params["forecast_id"],
            params["event_type"],
            params["event_timestamp"],
            params["premium"],
        )
        for row in self.rows:
            if row == identity:
                return 0
        self.rows.append(identity)
        return 1


def _persist(db, *, observed_at, premium, source_ref="shot-1"):
    sql = recommendation_event_insert("MARK")
    params = {
        "forecast_id": "F1",
        "event_type": "MARK",
        "event_timestamp": observed_at,
        "premium": premium,
        "pnl_pct": None,
        "r_multiple": None,
        "source_ref": source_ref,
        "notes": None,
    }
    return db.execute(sql, params)


def test_identical_normalized_mark_replay_persists_once():
    db = InMemoryEventDb()
    assert _persist(db, observed_at="2026-09-15T11:14:00+00:00", premium=172.70) == 1
    assert _persist(db, observed_at="2026-09-15T11:14:00+00:00", premium=172.70) == 0
    assert len(db.rows) == 1


def test_later_legitimate_mark_is_not_suppressed():
    db = InMemoryEventDb()
    assert _persist(db, observed_at="2026-09-15T11:14:00+00:00", premium=172.70) == 1
    assert _persist(db, observed_at="2026-09-15T11:19:00+00:00", premium=180.00, source_ref="shot-2") == 1
    assert len(db.rows) == 2


def test_same_timestamp_changed_premium_is_distinct_market_observation():
    db = InMemoryEventDb()
    assert _persist(db, observed_at="2026-09-15T11:14:00+00:00", premium=172.70) == 1
    assert _persist(db, observed_at="2026-09-15T11:14:00+00:00", premium=173.00, source_ref="shot-corrected") == 1
    assert len(db.rows) == 2
