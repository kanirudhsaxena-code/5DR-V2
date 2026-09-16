"""Freeze one exact-cutoff structured evidence capture for G11.

The runner may wait briefly for the approved 09:45 IST cutoff. It stores the immutable
bundle and its G11 capture metadata only in the GitHub Actions workspace/cache. It does
not publish a forecast, write canonical/production state, or trade.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.g11_live_capture import build_structured_capture, schedule_capture
from experiments.live_shadow_bundle_option_enrichment import build_live_shadow_bundle
from experiments.upstox_safe_diagnostics import diagnostic_code

IST = ZoneInfo("Asia/Kolkata")
OUTPUT_DIR = Path(".shadow/g11_capture")
BUNDLE_FILE = OUTPUT_DIR / "bundle.json"
CAPTURE_FILE = OUTPUT_DIR / "capture.json"


def run():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
    if not token:
        raise DataArchitectureError("G11 Upstox token missing")
    initial = schedule_capture(datetime.now(IST))
    if initial["wait_seconds"]:
        time.sleep(initial["wait_seconds"])
    started = datetime.now(IST)
    schedule = schedule_capture(started)
    bundle = build_live_shadow_bundle(token)
    capture = build_structured_capture(bundle, schedule, started)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_FILE.write_text(json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str), encoding="utf-8")
    CAPTURE_FILE.write_text(json.dumps(capture, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    result = {
        "status": "G11_STRUCTURED_EVIDENCE_CAPTURED",
        "pair_id": capture["comparison_window_id"],
        "session_date_ist": capture["session_date_ist"],
        "evidence_cutoff_ist": capture["evidence_cutoff_ist"],
        "capture_started_at_ist": capture["capture_started_at_ist"],
        "bundle_frozen_at_ist": capture["bundle_frozen_at_ist"],
        "capture_start_lag_seconds": capture["capture_start_lag_seconds"],
        "bundle_freeze_lag_seconds": capture["bundle_freeze_lag_seconds"],
        "bundle_sha256": capture["bundle_sha256"],
        "capture_sha256": capture["capture_sha256"],
        "source_mode": "UPSTOX_STRUCTURED",
        "bundle_persisted_to_repo": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_enabled": False,
        "canonical_integration_enabled": False,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"pair_id={capture['comparison_window_id']}\n")
            handle.write(f"bundle_sha256={capture['bundle_sha256']}\n")
            handle.write(f"capture_sha256={capture['capture_sha256']}\n")
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
