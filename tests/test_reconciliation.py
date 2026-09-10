from src.reconciliation import recommendation_primary_state


def test_untriggered_without_events():
    assert recommendation_primary_state([])["status"] == "UNTRIGGERED"


def test_t1_before_sl_is_win():
    state = recommendation_primary_state([
        {"event_id": 1, "event_timestamp": 1, "event_type": "ENTRY_TRIGGERED"},
        {"event_id": 2, "event_timestamp": 2, "event_type": "T1_HIT"},
        {"event_id": 3, "event_timestamp": 3, "event_type": "SL_HIT"},
    ])
    assert state == {"status": "T1_HIT", "primary_outcome": "WIN"}


def test_sl_before_t1_is_loss():
    state = recommendation_primary_state([
        {"event_id": 1, "event_timestamp": 1, "event_type": "ENTRY_TRIGGERED"},
        {"event_id": 2, "event_timestamp": 2, "event_type": "SL_HIT"},
        {"event_id": 3, "event_timestamp": 3, "event_type": "T1_HIT"},
    ])
    assert state == {"status": "SL_HIT", "primary_outcome": "LOSS"}
