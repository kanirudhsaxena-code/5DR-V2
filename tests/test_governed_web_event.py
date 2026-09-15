from datetime import datetime, timedelta, timezone

import pytest

from src.governed_web_event import ResearchObservation, WebResearchBlocked, build_web_research_packet

NOW = datetime(2026, 9, 15, 14, 30, tzinfo=timezone.utc)


def obs(**changes):
    values = dict(
        source_name='Reuters',
        source_ref='research:reuters:2026-09-15:nifty-close',
        authority='REPUTABLE_SECONDARY',
        observed_at=NOW - timedelta(minutes=2),
        captured_at=NOW - timedelta(minutes=1),
        fact='NIFTY market context independently verified',
        verified=True,
    )
    values.update(changes)
    return ResearchObservation(**values)


def test_builds_canonical_web_research_packet_without_price_inference():
    packet = build_web_research_packet('F1', 'PE', [obs()], now=NOW)
    assert packet.source_type == 'WEB_RESEARCH'
    assert packet.verified is True
    assert packet.fresh is True
    assert packet.premium is None
    assert packet.strike is None
    assert packet.expiry is None
    assert packet.contract_matched is False
    assert packet.continuous_path is False
    assert packet.source_ref.startswith('5dr:web-research#sha256=')


def test_empty_research_fails_closed():
    with pytest.raises(WebResearchBlocked, match='RESEARCH_EMPTY'):
        build_web_research_packet('F1', 'PE', [], now=NOW)


def test_unverified_research_fails_closed():
    with pytest.raises(WebResearchBlocked, match='RESEARCH_NOT_VERIFIED'):
        build_web_research_packet('F1', 'PE', [obs(verified=False)], now=NOW)


def test_stale_research_fails_closed():
    with pytest.raises(WebResearchBlocked, match='RESEARCH_STALE'):
        build_web_research_packet('F1', 'PE', [obs(captured_at=NOW - timedelta(hours=1), observed_at=NOW - timedelta(hours=1, minutes=1))], now=NOW)


def test_naive_timestamp_fails_closed():
    with pytest.raises(WebResearchBlocked, match='RESEARCH_TIMESTAMP_NAIVE'):
        build_web_research_packet('F1', 'PE', [obs(observed_at=datetime(2026, 9, 15, 14, 28))], now=NOW)


def test_research_packet_cannot_be_converted_to_option_event():
    packet = build_web_research_packet('F1', 'PE', [obs()], now=NOW)
    with pytest.raises(ValueError, match='OPTION_PREMIUM_MISSING'):
        packet.to_option_evidence()
