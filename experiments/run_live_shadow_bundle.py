"""Create the frozen live V2.2.3 shadow bundle without publishing it."""
import json
import os
from pathlib import Path

from experiments.live_shadow_bundle_option_enrichment import build_live_shadow_bundle, build_public_judgment_summary
from experiments.upstox_safe_diagnostics import diagnostic_code

OUTPUT = Path(".shadow/live_bundle.json")


def run():
    bundle = build_live_shadow_bundle(os.environ.get("UPSTOX_ANALYTICS_TOKEN", ""))
    if bundle.get("status") != "READY":
        raise ValueError("live evidence bundle is not READY")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str), encoding="utf-8")
    summary = build_public_judgment_summary(bundle)
    result = {
        "status": "LIVE_FROZEN_EVIDENCE_BUNDLE_READY",
        "bundle_sha256": bundle["bundle_sha256"],
        "run_id": bundle["run_id"],
        "coverage": bundle["coverage"],
        "judgment_summary": summary,
        "option_execution_evidence_enriched": bool(bundle.get("runtime_context", {}).get("option_execution_evidence_enriched")),
        "bundle_persisted_to_repo": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_enabled": False,
        "canonical_integration_enabled": False,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), default=str))
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"bundle_sha256={bundle['bundle_sha256']}\n")
            handle.write(f"run_id={bundle['run_id']}\n")
    return result


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(json.dumps({
            "status": "BLOCKED",
            "diagnostic_code": diagnostic_code(error),
            "bundle_persisted_to_repo": False,
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
