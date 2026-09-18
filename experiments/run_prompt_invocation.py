"""CLI entry point for governed 5DR prompt invocation planning."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from experiments.prompt_invocation import PromptInvocation, plan_prompt_invocation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--requested-at", required=True)
    args = parser.parse_args(argv)
    try:
        requested_at = datetime.fromisoformat(args.requested_at)
        result = plan_prompt_invocation(PromptInvocation(
            command=args.command,
            requested_at=requested_at,
            request_id=args.request_id,
        ))
    except Exception as exc:
        print(json.dumps({"status":"BLOCKED","error":str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "READY_TO_ACQUIRE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
