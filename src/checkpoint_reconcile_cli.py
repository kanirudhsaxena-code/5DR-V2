"""CLI for scheduled canonical D+1..D+5 checkpoint reconciliation."""
from __future__ import annotations

import json
import os

from .checkpoint_reconciliation import reconcile_due_checkpoints


def main() -> int:
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    token = (os.environ.get("UPSTOX_ANALYTICS_TOKEN") or "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if not token:
        raise SystemExit("UPSTOX_ANALYTICS_TOKEN is required")

    import psycopg2

    conn = psycopg2.connect(database_url)
    try:
        summary = reconcile_due_checkpoints(conn, token)
        print(json.dumps(
            {
                "status": "CHECKPOINT_RECONCILIATION_COMPLETE",
                "summary": summary.to_dict(),
                "trading_enabled": False,
                "forecast_methodology_changed": False,
            },
            sort_keys=True,
            default=str,
        ))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
