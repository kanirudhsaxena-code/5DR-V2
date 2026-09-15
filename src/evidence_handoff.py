"""Validated file handoff for normalized 5DR V2.2.2 EvidencePackets.

This module does not interpret screenshots or research the web. ChatGPT/5DR remains
the intelligence layer. It only accepts already-normalized JSON packets and converts
them into the approved EvidencePacket contract, failing closed on malformed input.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .evidence_bridge import EvidencePacket, SourceType

_ALLOWED_KEYS = {
    'forecast_id','source_type','source_ref','observed_at','captured_at','instrument',
    'strike','expiry','premium','verified','fresh','contract_matched','continuous_path','notes'
}


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('evidence timestamps must be timezone-aware')
    return parsed


def packet_from_dict(raw: dict) -> EvidencePacket:
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise ValueError(f'unknown evidence fields: {sorted(unknown)}')
    required = {'forecast_id','source_type','source_ref','observed_at','instrument','premium','verified','fresh','contract_matched'}
    missing = required - set(raw)
    if missing:
        raise ValueError(f'missing evidence fields: {sorted(missing)}')
    return EvidencePacket(
        forecast_id=raw['forecast_id'],
        source_type=SourceType(raw['source_type']),
        source_ref=raw['source_ref'],
        observed_at=_dt(raw['observed_at']),
        captured_at=_dt(raw.get('captured_at')),
        instrument=raw['instrument'],
        strike=float(raw['strike']) if raw.get('strike') is not None else None,
        expiry=raw.get('expiry'),
        premium=float(raw['premium']),
        verified=raw['verified'] is True,
        fresh=raw['fresh'] is True,
        contract_matched=raw['contract_matched'] is True,
        continuous_path=raw.get('continuous_path') is True,
        notes=raw.get('notes'),
    )


def load_packets(path: str | Path) -> list[EvidencePacket]:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('evidence handoff must be a JSON array')
    packets = [packet_from_dict(item) for item in data]
    ids = [p.forecast_id for p in packets]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate forecast_id in evidence handoff')
    return packets
