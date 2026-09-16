"""Execute the existing 5DR engine against the macro-enriched exact live bundle."""
import json
from pathlib import Path

from experiments.autonomous_shadow import run_structured_shadow
from experiments.macro_enriched_shadow_judgment import (
    EXPECTED_BUNDLE_SHA256,
    build_macro_enriched_judgment,
)

BUNDLE_PATH = Path(".shadow/live_bundle.json")


def run():
    if not BUNDLE_PATH.exists():
        raise ValueError("macro-enriched frozen bundle cache was not restored")
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if bundle.get("bundle_sha256") != EXPECTED_BUNDLE_SHA256:
        raise ValueError("restored bundle does not match macro-enriched judgment SHA")
    judgment = build_macro_enriched_judgment(bundle["bundle_sha256"])
    shadow = run_structured_shadow(bundle, judgment)
    if shadow.get("status") != "SHADOW_COMPLETE":
        raise ValueError("macro-enriched shadow did not complete")
    for flag in (
        "published", "forecast_release_enabled", "production_5dr_write_enabled",
        "lifecycle_write_enabled", "trading_execution_enabled", "methodology_changed",
    ):
        if shadow.get(flag) is not False:
            raise ValueError(f"shadow isolation boundary crossed: {flag}")

    result = shadow["engine_result"]
    out = {
        "status": "MACRO_ENRICHED_LIVE_SHADOW_COMPLETE",
        "bundle_sha256": EXPECTED_BUNDLE_SHA256,
        "request_id": shadow["request_id"],
        "regime": judgment["normalized_engine_inputs"]["regime"],
        "component_scores": judgment["normalized_engine_inputs"]["component_scores"],
        "des5": result["des5"],
        "directional_label": result["directional_label"],
        "market_trust": result["market_trust"],
        "market_trust_band": result["market_trust_band"],
        "probabilities": result["probabilities"],
        "event_shock": judgment["normalized_engine_inputs"]["event_shock"],
        "execution_edge": result["execution_edge"],
        "expected_rr": judgment["normalized_engine_inputs"]["expected_rr"],
        "tradeable": result["tradeable"],
        "tradeability_blockers": result["tradeability_blockers"],
        "release_complete": False,
        "published": False,
        "forecast_release_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
        "recommendation_released": False,
    }
    print(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return out


if __name__ == "__main__":
    run()
