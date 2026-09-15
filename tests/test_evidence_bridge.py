from datetime import datetime, timedelta, timezone
import pytest

from src.evidence_bridge import EvidenceBridgeError, EvidencePacket, no_write_reason

NOW = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)


def packet(**overrides):
    data = dict(
        forecast_id='F1', source_type='SCREENSHOT', source_ref='upload:abc',
        observed_at=NOW, captured_at=NOW + timedelta(minutes=1),
        instrument='PE', strike=23500, expiry='2026-09-22', premium=180,
        verified=True, fresh=True, contract_matched=True, continuous_path=False,
    )
    data.update(overrides)
    return EvidencePacket(**data)


def test_verified_screenshot_converts_to_option_evidence():
    evidence = packet().to_option_evidence()
    assert evidence.instrument == 'PE'
    assert evidence.strike == 23500
    assert evidence.premium == 180
    assert evidence.continuous_path is False


def test_verified_web_research_is_allowed():
    evidence = packet(source_type='WEB_RESEARCH', source_ref='https://verified.example/evidence').to_option_evidence()
    assert evidence.source_ref.startswith('https://')


@pytest.mark.parametrize('field,value,reason', [
    ('verified', False, 'EVIDENCE_NOT_VERIFIED'),
    ('fresh', False, 'EVIDENCE_STALE'),
    ('contract_matched', False, 'OPTION_CONTRACT_NOT_MATCHED'),
])
def test_invalid_evidence_fails_closed(field, value, reason):
    assert no_write_reason(packet(**{field: value})) == reason


def test_unknown_source_is_rejected():
    assert no_write_reason(packet(source_type='UPSTOX')) == 'SOURCE_NOT_ALLOWED'


def test_naive_timestamp_is_rejected():
    assert no_write_reason(packet(observed_at=datetime(2026, 9, 15, 10))) == 'TIMESTAMP_NOT_TIMEZONE_AWARE'


def test_snapshot_never_claims_continuous_path_by_default():
    assert packet().to_option_evidence().continuous_path is False


def test_missing_contract_identity_cannot_drive_option_lifecycle():
    with pytest.raises(EvidenceBridgeError, match='OPTION_CONTRACT_NOT_MATCHED'):
        packet(expiry=None).to_option_evidence()
