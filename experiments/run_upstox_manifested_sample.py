"""Safe live wrapper that emits a sanitized sample plus acquisition manifest.

Read-only experimental path only. No database, lifecycle, forecast or trading writes.
"""
import json
import os

from experiments.upstox_acquire import AcquisitionStageError, acquire_live_sample, github_audit_context
from experiments.upstox_manifest import build_failure_manifest, build_success_manifest
from experiments.upstox_safe_diagnostics import diagnostic_code


def main():
    context = github_audit_context()
    try:
        sample = acquire_live_sample(os.getenv("UPSTOX_ANALYTICS_TOKEN"), audit_context=context)
        manifest = build_success_manifest(sample)
        output = {
            "status": "MANIFESTED_LIVE_SAMPLE_PASSED",
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "sample": sample,
            "acquisition_manifest": manifest,
        }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except AcquisitionStageError as failure:
        code = diagnostic_code(failure.error)
        output = {
            "status": "BLOCKED",
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "acquisition_manifest": build_failure_manifest(failure.stage, code, context),
        }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
