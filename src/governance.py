"""Forecast-governance helpers for 5DR V2.1."""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
WINDOW_START = time(15, 20)
WINDOW_END = time(9, 14, 59)

@dataclass(frozen=True)
class Candidate:
    forecast_id: str
    issued_at: datetime
    valid: bool

def classify_run(local_dt: datetime) -> str:
    """Classify by IST clock time. Target trading date is resolved separately."""
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=IST)
    local_dt = local_dt.astimezone(IST)
    t = local_dt.time()
    if t >= WINDOW_START or t <= WINDOW_END:
        return "CANONICAL_CANDIDATE"
    return "INTRADAY_SNAPSHOT"

def latest_valid_candidate(candidates: Iterable[Candidate]) -> Optional[Candidate]:
    valid = [c for c in candidates if c.valid]
    return max(valid, key=lambda c: c.issued_at) if valid else None

def stability_score(directional_flips: int) -> float:
    if directional_flips < 0:
        raise ValueError("directional_flips cannot be negative")
    return float(max(0, 100 - 25 * directional_flips))

def revision_brier_improvement(prior_brier: float, later_brier: float) -> float:
    return round(float(prior_brier) - float(later_brier), 6)

def d1_policy(run_class: str) -> str:
    if run_class == "CANONICAL_CANDIDATE":
        return "TARGET_TRADING_DATE"
    if run_class == "INTRADAY_SNAPSHOT":
        return "NEXT_FULL_TRADING_SESSION"
    raise ValueError("unknown run class")
