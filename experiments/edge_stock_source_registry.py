"""Source registry and health contract for EDGE_STOCK fallback evidence.

This is execution-layer resilience only. It contains no scoring, forecasting,
recommendation, lifecycle persistence or trading semantics.
"""
from copy import deepcopy
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError

SOURCES = {
    "NSE_ANNOUNCEMENTS": {
        "type": "EXCHANGE",
        "authority": "OFFICIAL",
        "priority": 10,
        "base_url": "https://www.nseindia.com",
        "role": "NSE_DISCLOSURE",
    },
    "NSE_LARGE_DEALS": {
        "type": "EXCHANGE",
        "authority": "OFFICIAL",
        "priority": 10,
        "base_url": "https://www.nseindia.com",
        "role": "NSE_BLOCK_BULK",
    },
    "BSE_ANNOUNCEMENTS": {
        "type": "EXCHANGE",
        "authority": "OFFICIAL",
        "priority": 10,
        "base_url": "https://api.bseindia.com",
        "role": "BSE_DISCLOSURE",
    },
    "SEBI_ORDERS": {
        "type": "REGULATORY",
        "authority": "OFFICIAL",
        "priority": 5,
        "base_url": "https://www.sebi.gov.in",
        "role": "SEBI_ORDER",
    },
    "SCREENER_PEER_COHORT": {
        "type": "REPUTABLE_SECONDARY",
        "authority": "SECONDARY",
        "priority": 50,
        "base_url": "https://www.screener.in",
        "role": "PEER_COHORT",
    },
}


def source_registry():
    return deepcopy(SOURCES)


def build_source_health(*, source_name, url, checked_at, success,
                        error=None, recovery_attempt=None,
                        fallback=None, final_status=None):
    if source_name not in SOURCES:
        raise DataArchitectureError("EDGE_STOCK source name invalid")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise DataArchitectureError("EDGE_STOCK source URL invalid")
    if not url.startswith(SOURCES[source_name]["base_url"]):
        raise DataArchitectureError("EDGE_STOCK source URL outside registry")
    if not isinstance(success, bool):
        raise DataArchitectureError("EDGE_STOCK source success flag invalid")
    if isinstance(checked_at, datetime):
        parsed = checked_at
    elif isinstance(checked_at, str):
        try:
            parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        except ValueError:
            raise DataArchitectureError("EDGE_STOCK source health timestamp invalid") from None
    else:
        raise DataArchitectureError("EDGE_STOCK source health timestamp invalid")
    if parsed.tzinfo is None:
        raise DataArchitectureError("EDGE_STOCK source health timestamp naive")
    state = final_status or ("SUCCESS" if success else "FAILED")
    if state not in {"SUCCESS","FAILED","RECOVERED_VIA_FALLBACK","VERIFIED_PARTIAL"}:
        raise DataArchitectureError("EDGE_STOCK source final status invalid")
    meta = SOURCES[source_name]
    return {
        "name": source_name,
        "url": url,
        "type": meta["type"],
        "authority": meta["authority"],
        "priority": meta["priority"],
        "role": meta["role"],
        "timestamp": parsed.astimezone(timezone.utc).isoformat(),
        "success": success,
        "error": error,
        "recovery_attempt": recovery_attempt,
        "fallback": fallback,
        "final_status": state,
    }
