"""Execute the approved G11 next-session rollover using existing read-only components.

This is composition-only plumbing. It does not change acquisition, freshness, expiry,
hashing, 5DR methodology, production state, lifecycle state, or trading capability.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.g11_live_capture import build_structured_capture, schedule_capture
from experiments.g11_rollover import ROLLOVER_GATE, validate_next_session_rollover
from experiments.live_shadow_bundle_option_enrichment import build_live_shadow_bundle
from experiments.upstox_safe_diagnostics import diagnostic_code
from experiments.upstox_session import get_nfo_market_status

IST = ZoneInfo("Asia/Kolkata")
SERIES_PATH = Path("experiments/gate_records/G11_manual_series_2026-09-17.json")
GATE_DIR = Path("experiments/gate_records")
OUTPUT_DIR = Path(".shadow/g11_rollover")
GATE_FILE = OUTPUT_DIR / "rollover_gate.json"
CAPTURE_FILE = OUTPUT_DIR / "capture.json"


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise DataArchitectureError(f"G11 rollover input unavailable: {path.name}") from exc


def _replay_bundle_sha(bundle):
    # Round-trip through canonical JSON, then independently recompute the frozen digest.
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    replayed = json.loads(canonical)
    supplied = str(replayed.pop("bundle_sha256", "")).lower()
    calculated = hashlib.sha256(
        json.dumps(replayed, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    if supplied != calculated:
        raise DataArchitectureError("G11 rollover bundle replay fingerprint mismatch")
    return calculated


def _active_expiries(bundle):
    records = bundle.get("quantitative_records")
    if not isinstance(records, list):
        raise DataArchitectureError("G11 rollover quantitative records missing")
    for record in records:
        if isinstance(record, dict) and record.get("variable_id") == "NIFTY_OPTION_CONTRACTS":
            values = record.get("values") if isinstance(record.get("values"), dict) else {}
            expiries = values.get("available_expiries")
            if isinstance(expiries, list) and expiries:
                return expiries
    raise DataArchitectureError("G11 rollover active expiries missing")


def _completed_rollover_keys():
    keys = []
    if not GATE_DIR.exists():
        return keys
    for path in sorted(GATE_DIR.glob("G11_rollover_*.json")):
        try:
            record = _load(path)
        except DataArchitectureError:
            continue
        if record.get("gate") == ROLLOVER_GATE and record.get("status") == "PASS":
            key = record.get("rollover_run_key")
            if isinstance(key, str) and key:
                keys.append(key)
    return keys


def run():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
    if not token:
        raise DataArchitectureError("G11 Upstox token missing")

    previous_series = _load(SERIES_PATH)
    started = datetime.now(IST)
    schedule = schedule_capture(started, manual_run_id="ROLLOVER")
    bundle = build_live_shadow_bundle(token)
    capture = build_structured_capture(bundle, schedule, started)

    # The live bundle already used the official NFO status and current option contract
    # universe. Re-read status independently for the rollover gate; derive expiries from
    # the frozen option-contract evidence itself.
    market_status = get_nfo_market_status(token)
    active_expiries = _active_expiries(bundle)
    replay_sha = _replay_bundle_sha(bundle)

    gate = validate_next_session_rollover(
        previous_series=previous_series,
        current_capture=capture,
        market_status=market_status,
        active_expiries=active_expiries,
        replay_bundle_sha256=replay_sha,
        completed_run_keys=_completed_rollover_keys(),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GATE_FILE.write_text(
        json.dumps(gate, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    CAPTURE_FILE.write_text(
        json.dumps(capture, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    result = {
        "status": "G11_NEXT_SESSION_ROLLOVER_PASS",
        "session_date": gate["session_date"],
        "rollover_run_key": gate["rollover_run_key"],
        "bundle_sha256": gate["evidence"]["bundle_sha256"],
        "capture_sha256": gate["evidence"]["capture_sha256"],
        "gate_sha256": gate["gate_sha256"],
        "selected_expiry": gate["evidence"]["selected_expiry"],
        "market_status": gate["evidence"]["market_status"],
        "published": False,
        "forecast_release_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
        "production_activation_allowed": False,
        "pr30_merge_allowed": False,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"session_date={gate['session_date']}\n")
            handle.write(f"rollover_run_key={gate['rollover_run_key']}\n")
            handle.write(f"bundle_sha256={gate['evidence']['bundle_sha256']}\n")
            handle.write(f"gate_sha256={gate['gate_sha256']}\n")
    return result


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(json.dumps({
            "status": "BLOCKED",
            "diagnostic_code": diagnostic_code(error),
            "published": False,
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_execution_enabled": False,
            "methodology_changed": False,
            "production_activation_allowed": False,
            "pr30_merge_allowed": False,
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
