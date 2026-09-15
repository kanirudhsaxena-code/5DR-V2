"""Run two isolated read-only Upstox acquisitions and enforce duplicate policy."""
import json
import os
import time

from experiments.upstox_acquire import AcquisitionStageError, acquire_live_sample, github_audit_context
from experiments.upstox_reliability import compare_snapshots
from phase1.upstox import safe_failure


def main():
    token = os.getenv("UPSTOX_ANALYTICS_TOKEN")
    try:
        delay = int(os.getenv("UPSTOX_RELIABILITY_DELAY_SECONDS", "75"))
    except ValueError:
        delay = -1
    if delay < 5 or delay > 180:
        print(json.dumps({
            "status": "BLOCKED",
            "stage": "PAIR_CONFIG",
            "diagnostic_code": "INVALID_DELAY",
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
        }, sort_keys=True))
        return 2

    try:
        first = acquire_live_sample(token, audit_context=github_audit_context())
        started = time.monotonic()
        time.sleep(delay)
        second = acquire_live_sample(token, audit_context=github_audit_context())
        elapsed = time.monotonic() - started
        comparison = compare_snapshots(first, second, elapsed)
        output = {
            "status": "RELIABILITY_PAIR_PASSED",
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "comparison": comparison,
            "first": {
                "snapshot_fingerprint": first["audit"]["snapshot_fingerprint"],
                "market_status": first["market_session"]["status"],
                "selected_expiry": first["selected_expiry"],
                "spot": first["underlying_spot_price"],
                "latest_candle": first["latest_intraday_candle"]["timestamp"],
                "freshness_mode": first["reliability"]["mode"],
            },
            "second": {
                "snapshot_fingerprint": second["audit"]["snapshot_fingerprint"],
                "market_status": second["market_session"]["status"],
                "selected_expiry": second["selected_expiry"],
                "spot": second["underlying_spot_price"],
                "latest_candle": second["latest_intraday_candle"]["timestamp"],
                "freshness_mode": second["reliability"]["mode"],
            },
        }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except AcquisitionStageError as failure:
        print(json.dumps({
            "status": "BLOCKED",
            "stage": failure.stage,
            "diagnostic_code": safe_failure(failure.error),
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
        }, sort_keys=True))
        return 2
    except Exception as error:
        # Never emit arbitrary exception text. Reliability failures are mapped to
        # a fixed diagnostic; provider payloads and credentials remain withheld.
        from phase1.upstox import PipelineError
        diagnostic = safe_failure(error) if isinstance(error, PipelineError) else "RELIABILITY_POLICY_FAILED"
        print(json.dumps({
            "status": "BLOCKED",
            "stage": "PAIR_COMPARE",
            "diagnostic_code": diagnostic,
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
