"""Fail-closed data-quality primitives for normalized Upstox quantitative evidence.

Pure validation only; no network, forecasts, database writes, or trading operations.
"""
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from phase1.upstox import PipelineError

USABLE_CLASSES = {
    "LIVE", "DELAYED_20S", "DELAYED_120S", "DELAYED_15M",
    "SESSION_FINAL", "HISTORICAL",
}
ALL_CLASSES = USABLE_CLASSES | {"STALE", "UNAVAILABLE"}


def aware_utc(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise PipelineError(f"{field} timestamp invalid") from None
    else:
        raise PipelineError(f"{field} timestamp missing")
    if parsed.tzinfo is None:
        raise PipelineError(f"{field} timestamp naive")
    return parsed.astimezone(timezone.utc)


def finite_number(value, field, *, allow_negative=False, allow_zero=True):
    if isinstance(value, bool) or value is None:
        raise PipelineError(f"{field} missing")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise PipelineError(f"{field} invalid") from None
    if not number.is_finite():
        raise PipelineError(f"{field} invalid")
    if not allow_negative and number < 0:
        raise PipelineError(f"{field} negative")
    if not allow_zero and number == 0:
        raise PipelineError(f"{field} zero")
    return number


def validate_ohlc(open_, high, low, close, *, volume=None, open_interest=None):
    o = finite_number(open_, "open", allow_zero=False)
    h = finite_number(high, "high", allow_zero=False)
    l = finite_number(low, "low", allow_zero=False)
    c = finite_number(close, "close", allow_zero=False)
    if not (l <= min(o, c) <= max(o, c) <= h):
        raise PipelineError("Invalid OHLC geometry")
    if volume is not None:
        finite_number(volume, "volume")
    if open_interest is not None:
        finite_number(open_interest, "open interest")
    return True


def validate_price(value, field="price"):
    finite_number(value, field, allow_zero=False)
    return True


def validate_nonnegative(value, field):
    finite_number(value, field)
    return True


def validate_change_oi(value, field="change_oi"):
    finite_number(value, field, allow_negative=True)
    return True


def classify_timestamp_freshness(provider_timestamp, acquisition_timestamp,
                                 latency_class, max_age_seconds):
    if latency_class not in ALL_CLASSES - {"STALE", "UNAVAILABLE"}:
        raise PipelineError("Latency class invalid")
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float)):
        raise PipelineError("Freshness threshold invalid")
    if not math.isfinite(max_age_seconds) or max_age_seconds < 0:
        raise PipelineError("Freshness threshold invalid")
    provider = aware_utc(provider_timestamp, "provider")
    acquired = aware_utc(acquisition_timestamp, "acquisition")
    age = (acquired - provider).total_seconds()
    if age < -60:
        raise PipelineError("Provider timestamp is in the future")
    if age > max_age_seconds:
        return "STALE"
    return latency_class


def require_global_freshness(provider_timestamp, acquisition_timestamp,
                             declared_latency_seconds, grace_seconds):
    if isinstance(declared_latency_seconds, bool) or declared_latency_seconds not in {20, 120, 900}:
        raise PipelineError("Global provider latency invalid")
    if isinstance(grace_seconds, bool) or not isinstance(grace_seconds, (int, float)):
        raise PipelineError("Global freshness grace invalid")
    if not math.isfinite(grace_seconds) or grace_seconds < 0:
        raise PipelineError("Global freshness grace invalid")
    label = {20: "DELAYED_20S", 120: "DELAYED_120S", 900: "DELAYED_15M"}[declared_latency_seconds]
    return classify_timestamp_freshness(
        provider_timestamp,
        acquisition_timestamp,
        label,
        declared_latency_seconds + grace_seconds,
    )
