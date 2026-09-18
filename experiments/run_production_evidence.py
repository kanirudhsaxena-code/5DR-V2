"""Produce one fail-closed V2.2.3 structured evidence artifact in an approved live window.

The output is evidence-only. It never publishes a forecast, writes canonical state,
writes lifecycle state, or enables trading.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.live_shadow_bundle_option_enrichment import (
    build_live_shadow_bundle,
    build_public_judgment_summary,
)
from experiments.production_evidence import build_production_evidence_audit
from experiments.upstox_safe_diagnostics import diagnostic_code

IST = ZoneInfo("Asia/Kolkata")
OUTPUT_DIR = Path(".production/evidence")
BUNDLE_FILE = OUTPUT_DIR / "bundle.json"
SUMMARY_FILE = OUTPUT_DIR / "judgment_summary.json"
AUDIT_FILE = OUTPUT_DIR / "audit.json"


def run():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip()
    if not token:
        raise ValueError("UPSTOX_ANALYTICS_TOKEN missing")

    now = datetime.now(IST)
    bundle = build_live_shadow_bundle(token)
    audit = build_production_evidence_audit(bundle, now)
    summary = build_public_judgment_summary(bundle)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_FILE.write_text(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    SUMMARY_FILE.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    AUDIT_FILE.write_text(
        json.dumps(audit, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )

    result = {
        "status": audit["status"],
        "label": audit["label"],
        "run_class": audit["run_class"],
        "session_date_ist": audit["session_date_ist"],
        "bundle_sha256": audit["bundle_sha256"],
        "bundle_run_id": audit["bundle_run_id"],
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            for key in ("label", "run_class", "session_date_ist", "bundle_sha256", "bundle_run_id"):
                handle.write(f"{key}={result[key]}\n")
    return result


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(json.dumps({
            "status": "BLOCKED",
            "diagnostic_code": diagnostic_code(error),
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_execution_enabled": False,
            "methodology_changed": False,
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
