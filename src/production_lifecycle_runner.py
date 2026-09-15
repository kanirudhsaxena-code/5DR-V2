"""Fail-closed production lifecycle runner for 5DR V2.2.2.

The runner consumes canonical recommendation rows plus normalized evidence packets.
It does not research the web, interpret screenshots, call broker APIs or place orders.
Database I/O is dependency-injected so production credentials stay outside this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from .evidence_bridge import EvidencePacket
from .lifecycle_bridge import BridgeResult, process_evidence_packet


@dataclass(frozen=True)
class RunItem:
    forecast_id: str
    lifecycle_status: str
    action_kinds: tuple[str, ...]
    persisted: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RunSummary:
    started_at: datetime
    finished_at: datetime
    writes_enabled: bool
    recommendations_seen: int
    evidence_packets_seen: int
    processed: int
    persisted: int
    no_write: int
    missing_evidence: int
    items: tuple[RunItem, ...]


def _recommendation_for_planner(row: dict) -> dict:
    """Map canonical lifecycle-view names to the planner's stable contract."""
    return {
        'forecast_id': row['forecast_id'],
        'action': row['recommendation'],
        'instrument': row['instrument'],
        'strike': float(row['strike']) if row.get('strike') is not None else None,
        'expiry': str(row['expiry'])[:10] if row.get('expiry') is not None else None,
        'entry': float(row['observed_premium']) if row.get('observed_premium') is not None else None,
        'stop': float(row['stop_premium']) if row.get('stop_premium') is not None else None,
        'target1': float(row['target1_premium']) if row.get('target1_premium') is not None else None,
        'target2': float(row['target2_premium']) if row.get('target2_premium') is not None else None,
    }


def run_lifecycle(
    recommendations: Iterable[dict],
    packets: Iterable[EvidencePacket],
    existing_event_types: Callable[[str], set[str]],
    *,
    execute_sql: Callable[[str, dict], int],
    writes_enabled: bool = False,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RunSummary:
    started = now()
    recs = list(recommendations)
    packet_list = list(packets)
    packet_by_forecast: dict[str, EvidencePacket] = {}
    duplicate_ids: set[str] = set()
    for packet in packet_list:
        if packet.forecast_id in packet_by_forecast:
            duplicate_ids.add(packet.forecast_id)
        else:
            packet_by_forecast[packet.forecast_id] = packet

    items: list[RunItem] = []
    persisted = no_write = missing = 0
    for row in recs:
        forecast_id = row['forecast_id']
        status = row.get('lifecycle_status') or 'OPEN'
        if forecast_id in duplicate_ids:
            items.append(RunItem(forecast_id, status, ('NO_WRITE',), 0, ('DUPLICATE_EVIDENCE_PACKET',)))
            no_write += 1
            continue
        packet = packet_by_forecast.get(forecast_id)
        if packet is None:
            items.append(RunItem(forecast_id, status, ('NO_WRITE',), 0, ('NO_EVIDENCE_PACKET',)))
            no_write += 1
            missing += 1
            continue
        result: BridgeResult = process_evidence_packet(
            _recommendation_for_planner(row), status, existing_event_types(forecast_id), packet,
            execute_sql=execute_sql, writes_enabled=writes_enabled,
        )
        kinds = tuple(action.kind for action in result.actions)
        reasons = result.execution.reasons
        items.append(RunItem(forecast_id, status, kinds, result.execution.persisted, reasons))
        persisted += result.execution.persisted
        if 'NO_WRITE' in kinds or result.execution.persisted == 0:
            no_write += 1

    return RunSummary(
        started_at=started, finished_at=now(), writes_enabled=writes_enabled,
        recommendations_seen=len(recs), evidence_packets_seen=len(packet_list),
        processed=len(items), persisted=persisted, no_write=no_write,
        missing_evidence=missing, items=tuple(items),
    )
