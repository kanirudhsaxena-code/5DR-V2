"""Governed 5DR autonomous evidence acquisition boundary.

Execution-layer only. This module does not score, forecast, trade, or mutate the
5DR framework. It converts verified provider observations into auditable
evidence envelopes and fails closed when critical evidence is absent/stale.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable

SYSTEM_CATEGORIES = ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")


class AcquisitionBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceObservation:
    category: str
    source_ref: str
    retrieved_at: str
    status: str = "VERIFIED"
    authority: str = "PRIMARY"
    fallback_used: bool = False
    detail: str | None = None

    def validate(self, now: datetime, max_age_seconds: int = 900) -> None:
        if self.category not in SYSTEM_CATEGORIES:
            raise AcquisitionBlocked("UNKNOWN_CATEGORY")
        if self.status not in {"VERIFIED", "DEGRADED", "UNAVAILABLE"}:
            raise AcquisitionBlocked("INVALID_STATUS")
        if self.status in {"VERIFIED", "DEGRADED"} and not self.source_ref.strip():
            raise AcquisitionBlocked("SOURCE_REF_REQUIRED")
        try:
            stamp = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise AcquisitionBlocked("INVALID_RETRIEVED_AT") from None
        if stamp.tzinfo is None:
            raise AcquisitionBlocked("NAIVE_RETRIEVED_AT")
        age = (now.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        if age < -60 or age > max_age_seconds:
            raise AcquisitionBlocked("STALE_EVIDENCE")


def build_evidence_envelope(request_id: str, observations: Iterable[SourceObservation], *, now: datetime | None = None) -> dict:
    if not request_id or not request_id.strip():
        raise AcquisitionBlocked("REQUEST_ID_REQUIRED")
    now = now or datetime.now(timezone.utc)
    items = list(observations)
    for item in items:
        item.validate(now)

    by_category: dict[str, list[SourceObservation]] = {category: [] for category in SYSTEM_CATEGORIES}
    for item in items:
        by_category[item.category].append(item)

    missing = [category for category, values in by_category.items() if not values]
    unavailable = [category for category, values in by_category.items() if values and all(v.status == "UNAVAILABLE" for v in values)]
    conflicts = []
    for category, values in by_category.items():
        usable = [v for v in values if v.status in {"VERIFIED", "DEGRADED"}]
        if len({(v.authority, v.detail) for v in usable if v.detail is not None}) > 1:
            conflicts.append(category)

    blocked = sorted(set(missing + unavailable + conflicts))
    status = "AUTONOMOUS_EVIDENCE_BLOCKED" if blocked else "AUTONOMOUS_EVIDENCE_READY"
    return {
        "request_id": request_id,
        "status": status,
        "trading_enabled": False,
        "forecast_release_enabled": False,
        "assessed_at": now.astimezone(timezone.utc).isoformat(),
        "required_categories": list(SYSTEM_CATEGORIES),
        "items": [asdict(item) for item in items],
        "blockers": {"missing": missing, "unavailable": unavailable, "conflicts": conflicts},
    }
