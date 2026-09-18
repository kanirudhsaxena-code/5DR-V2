"""Governed official-web/research evidence normalization for EDGE_STOCK.

This module normalizes externally acquired facts into the shared data contract.
It does not browse, score, recommend, persist canonical state, or trade.
"""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record

VARIABLE_SOURCE_RULES = {
    "STOCK_FORWARD_CATALYSTS": {
        "allowed_roles": {"COMPANY_IR", "NSE_DISCLOSURE", "BSE_DISCLOSURE"},
        "minimum_distinct_roles": 1,
    },
    "STOCK_GOVERNANCE_RISK": {
        "allowed_roles": {"SEBI_ORDER", "NSE_DISCLOSURE", "BSE_DISCLOSURE", "COMPANY_IR"},
        "minimum_distinct_roles": 2,
    },
    "STOCK_INSTITUTIONAL_EVENTS": {
        "allowed_roles": {"NSE_BLOCK_BULK", "BSE_BLOCK_BULK", "NSE_DISCLOSURE", "BSE_DISCLOSURE"},
        "minimum_distinct_roles": 1,
    },
}

VALID_STATUSES = {
    "COMPLETE",
    "VERIFIED_PARTIAL",
    "CONFLICTED",
    "UNAVAILABLE",
    "RECOVERED_VIA_FALLBACK",
}


def _aware(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} invalid")
    if parsed.tzinfo is None:
        raise DataArchitectureError(f"{field} timezone missing")
    return parsed.astimezone(timezone.utc)


def _source_item(item):
    if not isinstance(item, dict):
        raise DataArchitectureError("EDGE_STOCK research source invalid")
    role = item.get("role")
    url = item.get("url")
    authority = item.get("authority")
    source_sha256 = item.get("source_sha256")
    retrieved_at = item.get("retrieved_at")
    facts = item.get("facts")
    if not isinstance(role, str) or not role:
        raise DataArchitectureError("research source role invalid")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise DataArchitectureError("research source URL invalid")
    if not isinstance(authority, str) or not authority:
        raise DataArchitectureError("research source authority invalid")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256.lower()):
        raise DataArchitectureError("research source digest invalid")
    if not isinstance(facts, dict):
        raise DataArchitectureError("research source facts invalid")
    return {
        "role": role,
        "url": url,
        "authority": authority,
        "source_sha256": source_sha256.lower(),
        "retrieved_at": _aware(retrieved_at, "research retrieval").isoformat(),
        "facts": deepcopy(facts),
    }


def build_research_record(*, stock_identity, variable_id, sources, status,
                          acquisition_timestamp):
    if variable_id not in VARIABLE_SOURCE_RULES:
        raise DataArchitectureError("EDGE_STOCK research variable invalid")
    if status not in VALID_STATUSES:
        raise DataArchitectureError("EDGE_STOCK research status invalid")
    if status in {"CONFLICTED", "UNAVAILABLE"}:
        raise DataArchitectureError("conflicted/unavailable research cannot enter READY evidence")
    if not isinstance(stock_identity, dict) or stock_identity.get("kind") != "STOCK":
        raise DataArchitectureError("EDGE_STOCK research stock identity invalid")
    if not isinstance(sources, (list, tuple)) or not sources:
        raise DataArchitectureError("EDGE_STOCK research sources missing")

    normalized = [_source_item(item) for item in sources]
    rules = VARIABLE_SOURCE_RULES[variable_id]
    roles = {item["role"] for item in normalized}
    if not roles.issubset(rules["allowed_roles"]):
        raise DataArchitectureError("EDGE_STOCK research source role not permitted")
    if len(roles) < rules["minimum_distinct_roles"]:
        raise DataArchitectureError("EDGE_STOCK research source coverage insufficient")

    fingerprints = [item["source_sha256"] for item in normalized]
    if len(fingerprints) != len(set(fingerprints)):
        raise DataArchitectureError("duplicate EDGE_STOCK research source")

    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    latest = max(_aware(item["retrieved_at"], "research retrieval") for item in normalized)

    return build_record(
        provider_id="RESEARCH_RECONCILER",
        source_semantic="OFFICIAL_WEB",
        variable_id=variable_id,
        consumer="EDGE_STOCK",
        subject=stock_identity,
        metric="governed_external_fact_set",
        values={
            "reconciliation_status": status,
            "source_roles": sorted(roles),
            "sources": normalized,
            "judgment_applied": False,
        },
        timeframe="event",
        provider_timestamp=latest,
        acquisition_timestamp=acquisition_timestamp,
        freshness_status="LIVE",
        source_reference=f"EDGE_STOCK_RESEARCH:{variable_id}",
        source_sha256=digest,
    )
