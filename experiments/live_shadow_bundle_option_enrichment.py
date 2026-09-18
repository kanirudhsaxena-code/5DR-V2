"""Enrich the frozen live shadow bundle with documented Upstox option-chain Greeks/depth.

The existing live bundle already proves exact option identity and current quotes. This
layer adds the option-chain fields needed by the frozen Execution Edge judgment:
IV/theta/delta/gamma/vega plus best bid/ask and quantities. It rebuilds the normalized
NIFTY_OPTION_CHAIN record and then recomputes the immutable bundle digest. No scoring,
forecast release, persistence or trading is performed here.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.live_shadow_bundle_v3_quote_fix import (
    build_live_shadow_bundle as _build_base_bundle,
    build_public_judgment_summary,
)
from experiments.upstox_transport import CurlOpener
from phase1.upstox import ReadOnlyClient


def _sha(*values):
    clean = [str(v) for v in values if isinstance(v, str) and v]
    if not clean:
        raise DataArchitectureError("option enrichment source digest missing")
    return hashlib.sha256("|".join(sorted(clean)).encode()).hexdigest()


def _num_or_none(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _enrichment_by_strike(chain_envelope, selected_expiry):
    rows = chain_envelope.get("payload", {}).get("data")
    if not isinstance(rows, list) or not rows:
        raise DataArchitectureError("option enrichment chain missing")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("expiry") != selected_expiry:
            continue
        strike = row.get("strike_price")
        if not isinstance(strike, (int, float)) or isinstance(strike, bool):
            continue
        sides = {}
        for side, field in (("CE", "call_options"), ("PE", "put_options")):
            leg = row.get(field)
            if not isinstance(leg, dict):
                raise DataArchitectureError("option enrichment leg missing")
            market = leg.get("market_data") if isinstance(leg.get("market_data"), dict) else {}
            greeks = leg.get("option_greeks") if isinstance(leg.get("option_greeks"), dict) else {}
            key = leg.get("instrument_key")
            if not isinstance(key, str) or not key:
                raise DataArchitectureError("option enrichment identity missing")
            bid = _num_or_none(market.get("bid_price"))
            ask = _num_or_none(market.get("ask_price"))
            spread = None
            spread_pct = None
            if bid is not None and ask is not None and ask >= bid:
                spread = round(float(ask) - float(bid), 6)
                midpoint = (float(ask) + float(bid)) / 2.0
                if midpoint > 0:
                    spread_pct = round(100.0 * spread / midpoint, 6)
            sides[side] = {
                "instrument_key": key,
                "close_price": _num_or_none(market.get("close_price")),
                "bid_price": bid,
                "bid_qty": _num_or_none(market.get("bid_qty")),
                "ask_price": ask,
                "ask_qty": _num_or_none(market.get("ask_qty")),
                "bid_ask_spread": spread,
                "bid_ask_spread_pct_mid": spread_pct,
                "prev_oi": _num_or_none(market.get("prev_oi")),
                "iv": _num_or_none(greeks.get("iv")),
                "theta": _num_or_none(greeks.get("theta")),
                "delta": _num_or_none(greeks.get("delta")),
                "gamma": _num_or_none(greeks.get("gamma")),
                "vega": _num_or_none(greeks.get("vega")),
                "pop": _num_or_none(greeks.get("pop")),
            }
        result[float(strike)] = sides
    return result


def _rebuild_option_record(record, enrichment, chain_envelope):
    values = deepcopy(record["values"])
    sample = values.get("sample_strikes")
    if not isinstance(sample, list) or not sample:
        raise DataArchitectureError("option sample missing for enrichment")
    for row in sample:
        strike = row.get("strike")
        if not isinstance(strike, (int, float)) or isinstance(strike, bool):
            raise DataArchitectureError("option sample strike invalid")
        matched = enrichment.get(float(strike))
        if not matched:
            raise DataArchitectureError("option enrichment strike mismatch")
        for side in ("CE", "PE"):
            if row.get(side, {}).get("instrument_key") != matched[side]["instrument_key"]:
                raise DataArchitectureError("option enrichment instrument mismatch")
            row[side].update(matched[side])
    values["execution_evidence"] = {
        "greeks_preserved": True,
        "iv_preserved": True,
        "theta_preserved": True,
        "best_bid_ask_preserved": True,
        "spread_calculated_from_best_bid_ask": True,
        "source_semantics": "UPSTOX_OPTION_CHAIN_DOCUMENTED_FIELDS",
    }
    return build_record(
        provider_id=record["provider_id"],
        source_semantic=record["source_semantic"],
        variable_id=record["variable_id"],
        consumer=record["consumer"],
        subject=record["subject"],
        metric="atm_plus_minus_two_live_quotes_with_greeks_depth",
        values=values,
        timeframe=record["timeframe"],
        provider_timestamp=record["provider_timestamp"],
        acquisition_timestamp=datetime.now(timezone.utc),
        freshness_status=record["freshness_status"],
        source_reference="UPSTOX_COMPOSITE:OPTION_CHAIN_EXACT_QUOTES_GREEKS_DEPTH",
        source_sha256=_sha(record["source_sha256"], chain_envelope["sha256"]),
        provider_latency_seconds=record.get("provider_latency_seconds"),
    )


def build_live_shadow_bundle(token):
    bundle = _build_base_bundle(token)
    if bundle.get("status") != "READY":
        raise DataArchitectureError("base live bundle not READY")
    runtime = bundle.get("runtime_context") or {}
    expiry = runtime.get("selected_nifty_expiry")
    if not isinstance(expiry, str) or not expiry:
        raise DataArchitectureError("selected expiry missing from live bundle")
    chain = ReadOnlyClient(token, opener=CurlOpener()).chain(expiry)
    enrichment = _enrichment_by_strike(chain, expiry)
    replaced = False
    records = []
    for record in bundle["quantitative_records"]:
        if record.get("variable_id") == "NIFTY_OPTION_CHAIN":
            records.append(_rebuild_option_record(record, enrichment, chain))
            replaced = True
        else:
            records.append(record)
    if not replaced:
        raise DataArchitectureError("NIFTY_OPTION_CHAIN record missing")
    bundle["quantitative_records"] = records
    bundle["runtime_context"]["option_execution_evidence_enriched"] = True
    bundle["runtime_context"]["option_execution_evidence_source_sha256"] = chain["sha256"]
    base = deepcopy(bundle)
    base.pop("bundle_sha256", None)
    bundle["bundle_sha256"] = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return bundle
