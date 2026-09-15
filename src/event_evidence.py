"""Governed event/shock source registry boundary for 5DR.

Network fetching is deliberately injected so tests remain deterministic and the
registry controls every allowed source. A failed source is never interpreted as
'no event'.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from src.autonomous_acquisition import SourceObservation


@dataclass(frozen=True)
class EventSource:
    name: str
    url: str
    authority: str
    priority: int


DEFAULT_EVENT_SOURCES = (
    EventSource("RBI", "https://www.rbi.org.in/", "OFFICIAL_REGULATORY", 1),
    EventSource("SEBI", "https://www.sebi.gov.in/", "OFFICIAL_REGULATORY", 1),
    EventSource("NSE", "https://www.nseindia.com/", "EXCHANGE", 2),
)


def acquire_event_observation(fetcher: Callable[[EventSource], tuple[bool, str]], sources=DEFAULT_EVENT_SOURCES) -> SourceObservation:
    failures = []
    for source in sorted(sources, key=lambda s: s.priority):
        ok, ref = fetcher(source)
        if ok and isinstance(ref, str) and ref.strip():
            return SourceObservation(
                category="EVENT_SHOCK",
                status="VERIFIED" if not failures else "DEGRADED",
                source_ref=ref,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                authority=source.authority,
                fallback_used=bool(failures),
                detail=f"Event/shock source registry verified via {source.name}; failed higher-priority sources={len(failures)}",
            )
        failures.append(source.name)
    return SourceObservation(
        category="EVENT_SHOCK",
        status="UNAVAILABLE",
        source_ref="",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        authority="SOURCE_REGISTRY",
        fallback_used=bool(failures),
        detail="All approved event sources unavailable; do not infer absence of events",
    )
