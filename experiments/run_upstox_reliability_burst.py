"""Run clustered read-only Upstox reliability checks across the market open.

Experimental only. No database, forecast, lifecycle or trading writes.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from experiments.upstox_acquire import AcquisitionStageError, acquire_live_sample, github_audit_context
from experiments.upstox_manifest import build_failure_manifest, build_success_manifest
from experiments.upstox_reliability import compare_snapshots
from phase1.upstox import PipelineError, safe_failure

IST = ZoneInfo("Asia/Kolkata")
CHECKPOINTS = ((9, 45), (10, 0), (10, 15), (10, 30))
PAIR_DELAY_SECONDS = 75
MAX_START_LATENESS_SECONDS = 300


def checkpoint_datetimes(now_ist):
    """Return today's four intended IST checkpoint datetimes."""
    return [
        now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for hour, minute in CHECKPOINTS
    ]


def _sleep_until(target):
    now = datetime.now(IST)
    wait = (target - now).total_seconds()
    if wait > 0:
        time.sleep(wait)
    return max(0.0, -wait)


def _run_checkpoint(label):
    context = github_audit_context()
    first = acquire_live_sample(os.getenv("UPSTOX_ANALYTICS_TOKEN"), audit_context=context)
    first_manifest = build_success_manifest(first)
    started = time.monotonic()
    time.sleep(PAIR_DELAY_SECONDS)
    second = acquire_live_sample(os.getenv("UPSTOX_ANALYTICS_TOKEN"), audit_context=context)
    second_manifest = build_success_manifest(second)
    elapsed = time.monotonic() - started
    comparison = compare_snapshots(first, second, elapsed)

    for sample in (first, second):
        if sample.get("market_session", {}).get("status") != "NORMAL_OPEN":
            raise PipelineError("Burst checkpoint is not NORMAL_OPEN")
        if sample.get("reliability", {}).get("status") != "FRESHNESS_PASS":
            raise PipelineError("Burst checkpoint freshness failed")
        if sample.get("reliability", {}).get("mode") != "LIVE_OPEN":
            raise PipelineError("Burst checkpoint is not LIVE_OPEN")
    if comparison.get("duplicate") is True:
        raise PipelineError("Burst checkpoint did not advance")

    return {
        "label": label,
        "status": "PASS",
        "read_only": True,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
        "first_manifest_sha256": first_manifest["manifest_sha256"],
        "second_manifest_sha256": second_manifest["manifest_sha256"],
        "first_snapshot_fingerprint": first["audit"]["snapshot_fingerprint"],
        "second_snapshot_fingerprint": second["audit"]["snapshot_fingerprint"],
        "first_candle": first["latest_intraday_candle"]["timestamp"],
        "second_candle": second["latest_intraday_candle"]["timestamp"],
        "selected_expiry": second["selected_expiry"],
        "spot_first": first["underlying_spot_price"],
        "spot_second": second["underlying_spot_price"],
        "pair_elapsed_seconds": round(elapsed, 3),
        "comparison": comparison["classification"],
    }


def main():
    token = os.getenv("UPSTOX_ANALYTICS_TOKEN")
    now = datetime.now(IST)
    checkpoints = checkpoint_datetimes(now)
    results = []

    for target in checkpoints:
        label = target.strftime("%H:%M")
        lateness = _sleep_until(target)
        if lateness > MAX_START_LATENESS_SECONDS:
            failure = build_failure_manifest(
                "BURST_SCHEDULE",
                "CHECKPOINT_TOO_LATE",
                github_audit_context(),
            )
            print(json.dumps({"checkpoint": label, "manifest": failure}, sort_keys=True))
            return 2
        try:
            result = _run_checkpoint(label)
            result["start_lateness_seconds"] = round(lateness, 3)
            results.append(result)
            print(json.dumps({"checkpoint": result}, sort_keys=True, separators=(",", ":")))
        except AcquisitionStageError as error:
            failure = build_failure_manifest(error.stage, safe_failure(error.error), github_audit_context())
            print(json.dumps({"checkpoint": label, "manifest": failure}, sort_keys=True))
            return 2
        except PipelineError as error:
            failure = build_failure_manifest("BURST_POLICY", safe_failure(error), github_audit_context())
            print(json.dumps({"checkpoint": label, "manifest": failure}, sort_keys=True))
            return 2
        except Exception:
            failure = build_failure_manifest("BURST_POLICY", "RELIABILITY_POLICY_FAILED", github_audit_context())
            print(json.dumps({"checkpoint": label, "manifest": failure}, sort_keys=True))
            return 2

    summary = {
        "status": "BURST_RELIABILITY_PASSED",
        "read_only": True,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
        "checkpoint_count": len(results),
        "checkpoints": [row["label"] for row in results],
        "all_advanced": all(row["comparison"] == "ADVANCED" for row in results),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
