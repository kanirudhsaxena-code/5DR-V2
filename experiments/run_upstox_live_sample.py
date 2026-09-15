import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from experiments.upstox_sanitizer import sanitize_live_envelopes
from phase1.upstox import PipelineError, ReadOnlyClient


def main():
    try:
        client = ReadOnlyClient(os.getenv("UPSTOX_ANALYTICS_TOKEN"))
        contracts = client.contracts()
        intraday = client.intraday()
        expiries = sorted({row["expiry"] for row in contracts["payload"]["data"] if row.get("underlying_key") == "NSE_INDEX|Nifty 50"})
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        expiry = next(value for value in expiries if datetime.fromisoformat(value).date() >= today)
        chain = client.chain(expiry)
        result = sanitize_live_envelopes(contracts, intraday, chain, today)
        result["status"] = "LIVE_SAMPLE_PASSED"
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (PipelineError, ValueError, KeyError, TypeError, StopIteration):
        print(json.dumps({"status": "BLOCKED", "read_only": True, "trading_enabled": False, "production_5dr_write_enabled": False, "reason": "Authenticated acquisition or strict validation failed; provider payload and credentials withheld."}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
