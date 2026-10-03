"""Dedicated governed PREOPEN evidence bridge for EDGE Console / 5DR.

This path intentionally avoids normal-session intraday requirements before 09:15 IST.
It reuses the validated PREOPEN bundle, validates the live option-chain identity with
an empty-intraday-tolerant sanitizer, and emits only bounded structured evidence.
No forecast, canonical selection, lifecycle write, or trading action occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from experiments.live_shadow_bundle import _stamp
from experiments.preopen_acquire import acquire_preopen_bundle
from experiments.upstox_safe_diagnostics import diagnostic_code
from experiments.upstox_sanitizer import sanitize_live_envelopes
from experiments.upstox_transport import CurlOpener
from phase1.upstox import NIFTY, PipelineError, ReadOnlyClient

SCHEMA = "5dr-console-market-evidence-v1"
PROVIDER = "UPSTOX"


def _sha(*values: object) -> str:
    payload = "|".join(str(v) for v in values if v is not None)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _observation(category: str, ref: str, captured_at: str, structured_data: dict, *, verification: str = "VERIFIED", findings=None, limitations=None) -> dict:
    return {
        "category": category,
        "source_kind": "UPSTOX_STRUCTURED",
        "source_ref": ref,
        "observed_at": captured_at,
        "retrieved_at": captured_at,
        "verification": verification,
        "findings": list(findings or []),
        "structured_data": structured_data,
        "limitations": list(limitations or []),
    }


def _recent_daily_context(rows: list, target_date: date) -> dict:
    valid = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 7:
            raise PipelineError("Candle schema mismatch")
        stamp = _stamp(row[0])
        if stamp.date() < target_date:
            valid.append((stamp, row))
    if not valid:
        raise PipelineError("Historical daily candles are empty")
    valid.sort(key=lambda item: item[0])
    tail = [row for _, row in valid[-10:]]
    closes = [float(row[4]) for row in tail]
    highs = [float(row[2]) for row in tail]
    lows = [float(row[3]) for row in tail]
    return {
        "last_10_sessions": [
            {
                "timestamp": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
                "open_interest": row[6],
            }
            for row in tail
        ],
        "last_close": closes[-1],
        "ten_session_high": max(highs),
        "ten_session_low": min(lows),
        "five_session_return_pct": (
            round(100.0 * (closes[-1] / closes[-5] - 1.0), 6)
            if len(closes) >= 5 and closes[-5] != 0
            else None
        ),
    }


def build_console_preopen_payload(
    request_id: str,
    *,
    bundle: dict,
    sanitized_chain: dict,
    daily_context: dict,
    source_sha256: str,
) -> dict:
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("REQUEST_ID_MISSING")
    if bundle.get("schema") != "5dr-preopen-evidence-bundle-v1" or bundle.get("status") != "READY":
        raise ValueError("PREOPEN_BUNDLE_NOT_READY")
    side_effects = bundle.get("side_effects") or {}
    if any(side_effects.get(key) is not False for key in (
        "forecast_release_enabled",
        "production_5dr_write_enabled",
        "lifecycle_write_enabled",
        "trading_enabled",
        "canonical_integration_enabled",
        "methodology_changed",
    )):
        raise ValueError("PREOPEN_BUNDLE_CROSSED_GOVERNANCE_BOUNDARY")

    captured_at = str(bundle.get("frozen_at") or "")
    if not captured_at or "T" not in captured_at:
        raise ValueError("PREOPEN_BUNDLE_TIME_INVALID")
    digest = _sha(bundle.get("bundle_sha256"), source_sha256)
    base = f"upstox-bundle://{digest}"

    prior = (bundle.get("prior_close_record") or {}).get("values") or {}
    prior_close = prior.get("close")
    spot = sanitized_chain.get("underlying_spot_price")
    gap_pct = None
    if isinstance(prior_close, (int, float)) and isinstance(spot, (int, float)) and prior_close:
        gap_pct = round(100.0 * (float(spot) / float(prior_close) - 1.0), 6)

    sample = sanitized_chain.get("sample_strikes")
    if not isinstance(sample, list) or not sample:
        raise ValueError("PREOPEN_OPTION_SAMPLE_MISSING")

    observations = [
        _observation(
            "PRICE_TECHNICALS",
            base + "#preopen-price-technicals",
            captured_at,
            {
                "session_mode": "PREOPEN_MATCHING",
                "target_session_date": bundle.get("target_session_date"),
                "previous_session_date": bundle.get("previous_session_date"),
                "prior_session_final_ohlc": prior,
                "provider_underlying_spot": spot,
                "gap_pct_vs_prior_close": gap_pct,
                "recent_daily_context": daily_context,
                "normal_market_intraday_required": False,
            },
            findings=[
                {"label": "Prior Close", "value": prior_close},
                {"label": "Provider Underlying Spot", "value": spot},
                {"label": "Gap vs Prior Close %", "value": gap_pct},
            ],
            limitations=[
                "PREOPEN evidence intentionally excludes normal-session intraday candles before 09:15 IST."
            ],
        ),
        _observation(
            "DERIVATIVES_OI",
            base + "#preopen-derivatives-oi",
            captured_at,
            {
                "session_mode": "PREOPEN_MATCHING",
                "selected_expiry": sanitized_chain.get("selected_expiry"),
                "underlying_spot_price": spot,
                "sample_strikes": sample,
                "intraday_availability": sanitized_chain.get("intraday_availability"),
                "normal_market_intraday_required": False,
            },
        ),
        _observation(
            "MARKET_TRUST",
            base + "#preopen-market-trust",
            captured_at,
            {
                "session_mode": "PREOPEN_MATCHING",
                "overnight_records": bundle.get("overnight_records") or [],
                "external_evidence": bundle.get("external_evidence") or [],
                "previous_session_date": bundle.get("previous_session_date"),
            },
        ),
        _observation(
            "EXECUTION_RISK",
            base + "#preopen-execution-risk",
            captured_at,
            {
                "session_mode": "PREOPEN_MATCHING",
                "selected_expiry": sanitized_chain.get("selected_expiry"),
                "sample_strikes": sample,
                "normal_market_open": False,
                "execution_constraint": "PREOPEN_CANONICAL_ANALYSIS_ONLY",
            },
            verification="DEGRADED",
            limitations=[
                "Pre-open option liquidity and executable spreads can change materially at the 09:15 IST normal-market open."
            ],
        ),
    ]

    return {
        "schema": SCHEMA,
        "request_id": request_id.strip(),
        "status": "AUTOMATED_MARKET_DATA_READY",
        "provider": PROVIDER,
        "captured_at": captured_at,
        "bundle_sha256": digest,
        "session_mode": "PREOPEN_MATCHING",
        "target_session_date": bundle.get("target_session_date"),
        "trigger_type": "SCHEDULED",
        "evidence_mode": "PREOPEN",
        "market_session_as_of": bundle.get("previous_session_date"),
        "research_as_of": captured_at,
        "target_session": bundle.get("target_session_date"),
        "benchmark_role": "SESSION_PREOPEN",
        "observations": observations,
        "blockers": [],
        "trading_enabled": False,
        "forecast_release_enabled": False,
        "methodology_changed": False,
    }


def blocked_payload(request_id: str, code: str) -> dict:
    return {
        "schema": SCHEMA,
        "request_id": request_id,
        "status": "AUTOMATED_MARKET_DATA_BLOCKED",
        "provider": PROVIDER,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "session_mode": "PREOPEN_MATCHING",
        "observations": [],
        "blockers": [code],
        "trading_enabled": False,
        "forecast_release_enabled": False,
        "methodology_changed": False,
    }


def run(request_id: str) -> dict:
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip()
    if not token:
        return blocked_payload(request_id, "UPSTOX_TOKEN_MISSING")
    try:
        bundle, _audit = acquire_preopen_bundle(token)
        target = date.fromisoformat(str(bundle["target_session_date"]))
        expiry = str(bundle["active_derivative_expiry"])

        client = ReadOnlyClient(token, opener=CurlOpener())
        contracts = client.contracts()
        intraday = client.intraday()
        chain = client.chain(expiry)
        sanitized = sanitize_live_envelopes(
            contracts,
            intraday,
            chain,
            target,
            selected_expiry=expiry,
            allow_empty_intraday=True,
        )
        daily = client.daily(target - timedelta(days=30), target - timedelta(days=1))
        daily_context = _recent_daily_context(daily["payload"]["data"]["candles"], target)
        source_sha = _sha(
            contracts.get("sha256"),
            intraday.get("sha256"),
            chain.get("sha256"),
            daily.get("sha256"),
        )
        return build_console_preopen_payload(
            request_id,
            bundle=bundle,
            sanitized_chain=sanitized,
            daily_context=daily_context,
            source_sha256=source_sha,
        )
    except Exception as error:
        message = str(error)
        if "outside governed PREOPEN matching window" in message:
            code = "PREOPEN_WINDOW_INVALID"
        else:
            code = diagnostic_code(error)
        return blocked_payload(request_id, code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output", default="console_preopen_market_evidence.json")
    args = parser.parse_args()
    payload = run(args.request_id)
    Path(args.output).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "request_id": payload["request_id"],
        "status": payload["status"],
        "session_mode": payload.get("session_mode"),
        "blockers": payload["blockers"],
        "trading_enabled": False,
        "forecast_release_enabled": False,
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
