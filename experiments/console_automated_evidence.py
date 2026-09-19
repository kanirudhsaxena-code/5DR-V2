"""Bounded automated Upstox evidence handoff for EDGE Console.

This is an acquisition bridge only. It does not score, forecast, recommend, write
canonical 5DR state, or place trades. It reuses the validated screenshot-free
V2.2.3 structured evidence bundle and emits only the bounded facts the Console
intelligence layer needs.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from experiments.live_shadow_bundle_option_enrichment import (
    build_live_shadow_bundle,
    build_public_judgment_summary,
)
from experiments.upstox_safe_diagnostics import diagnostic_code

SCHEMA = "5dr-console-market-evidence-v1"
PROVIDER = "UPSTOX"


def _safe_side_effects(bundle: dict) -> None:
    if bundle.get("status") != "READY":
        raise ValueError("BUNDLE_NOT_READY")
    screenshot = bundle.get("screenshot_policy")
    if not isinstance(screenshot, dict) or screenshot.get("screenshot_dependency") is not False:
        raise ValueError("SCREENSHOT_DEPENDENCY_PRESENT")
    for field in ("forecast_released", "production_5dr_write_enabled", "trading_enabled"):
        if bundle.get(field) is not False:
            raise ValueError("ACQUISITION_CROSSED_RELEASE_BOUNDARY")
    runtime = bundle.get("runtime_context")
    if isinstance(runtime, dict):
        for field in (
            "forecast_release_enabled",
            "production_5dr_write_enabled",
            "lifecycle_write_enabled",
            "trading_enabled",
            "canonical_integration_enabled",
            "methodology_changed",
        ):
            if runtime.get(field) is not False:
                raise ValueError("ACQUISITION_CROSSED_RUNTIME_BOUNDARY")


def _observation(category: str, ref: str, captured_at: str, structured_data: dict, findings=None) -> dict:
    return {
        "category": category,
        "source_kind": "UPSTOX_STRUCTURED",
        "source_ref": ref,
        "observed_at": captured_at,
        "retrieved_at": captured_at,
        "verification": "VERIFIED",
        "findings": list(findings or []),
        "structured_data": structured_data,
        "limitations": [],
    }


def build_console_payload(request_id: str, bundle: dict, summary: dict) -> dict:
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("REQUEST_ID_MISSING")
    _safe_side_effects(bundle)
    digest = bundle.get("bundle_sha256")
    frozen_at = bundle.get("frozen_at")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("BUNDLE_DIGEST_INVALID")
    if not isinstance(frozen_at, str):
        raise ValueError("BUNDLE_TIME_INVALID")

    nifty = summary.get("nifty") or {}
    spot = nifty.get("spot") if isinstance(nifty, dict) else {}
    current_price = spot.get("last_price") if isinstance(spot, dict) else None
    option_chain = summary.get("option_chain") or {}
    underlying = option_chain.get("underlying_spot_price") if isinstance(option_chain, dict) else None

    base = f"upstox-bundle://{digest}"
    observations = [
        _observation(
            "PRICE_TECHNICALS",
            base + "#price-technicals",
            frozen_at,
            {
                "nifty": summary.get("nifty"),
                "chart": summary.get("chart"),
            },
            [{"label": "Current Price", "value": current_price}] if current_price is not None else [],
        ),
        _observation(
            "DERIVATIVES_OI",
            base + "#derivatives-oi",
            frozen_at,
            {
                "nifty_futures": summary.get("nifty_futures"),
                "option_chain": option_chain,
                "derivative_analytics": summary.get("derivative_analytics"),
            },
            [{"label": "Underlying Value", "value": underlying}] if underlying is not None else [],
        ),
        _observation(
            "MARKET_TRUST",
            base + "#market-trust",
            frozen_at,
            {
                "india_vix": summary.get("india_vix"),
                "heavyweights": summary.get("heavyweights"),
                "sectors": summary.get("sectors"),
                "fii_dii_cash": summary.get("fii_dii_cash"),
                "fii_index_derivatives": summary.get("fii_index_derivatives"),
                "global_risk": summary.get("global_risk"),
                "crude_usdinr": summary.get("crude_usdinr"),
            },
        ),
        _observation(
            "EXECUTION_RISK",
            base + "#execution-risk",
            frozen_at,
            {
                "selected_expiry": option_chain.get("selected_expiry") if isinstance(option_chain, dict) else None,
                "sample_strikes": option_chain.get("sample_strikes") if isinstance(option_chain, dict) else None,
                "derivative_analytics": summary.get("derivative_analytics"),
            },
        ),
    ]

    return {
        "schema": SCHEMA,
        "request_id": request_id.strip(),
        "status": "AUTOMATED_MARKET_DATA_READY",
        "provider": PROVIDER,
        "captured_at": frozen_at,
        "bundle_sha256": digest,
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
        bundle = build_live_shadow_bundle(token)
        summary = build_public_judgment_summary(bundle)
        return build_console_payload(request_id, bundle, summary)
    except Exception as error:
        return blocked_payload(request_id, diagnostic_code(error))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output", default="console_market_evidence.json")
    args = parser.parse_args()
    payload = run(args.request_id)
    Path(args.output).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "request_id": payload["request_id"],
            "status": payload["status"],
            "provider": payload["provider"],
            "blockers": payload["blockers"],
            "trading_enabled": False,
            "forecast_release_enabled": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
