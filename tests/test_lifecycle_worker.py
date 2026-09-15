from datetime import date
from src.lifecycle_worker import derive_events, checkpoint_due, should_process


def test_t2_mark_emits_t1_and_t2():
    events = derive_events(entry=100, stop=80, target1=130, target2=150,
                           mark=160, existing_types=set())
    assert [e["event_type"] for e in events] == ["T1_HIT", "T2_HIT"]
    assert events[-1]["pnl_pct"] == 50.0
    assert events[-1]["r_multiple"] == 2.5


def test_stop_emits_loss_event():
    events = derive_events(entry=100, stop=80, target1=130, target2=150,
                           mark=75, existing_types=set())
    assert events[0]["event_type"] == "SL_HIT"
    assert events[0]["r_multiple"] == -1.0


def test_idempotent_existing_target():
    events = derive_events(entry=100, stop=80, target1=130, target2=150,
                           mark=160, existing_types={"T1_HIT", "T2_HIT"})
    assert events == []


def test_checkpoint_due_only_when_due():
    assert checkpoint_due(date(2026, 9, 15), date(2026, 9, 15), "DUE")
    assert not checkpoint_due(date(2026, 9, 16), date(2026, 9, 15), "DUE")
    assert not checkpoint_due(date(2026, 9, 15), date(2026, 9, 15), "CAPTURED")


def test_closed_not_processed():
    assert should_process("BUY_PE", "OPEN")
    assert not should_process("BUY_PE", "CLOSED_T2")
    assert not should_process("NO_TRADE", "OPEN")
