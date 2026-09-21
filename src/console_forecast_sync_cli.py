"""Synchronize complete published EDGE Console 5DR runs into canonical persistence
from the governed public handoff state branch.

No Cloudflare credential is required in the 5DR repository. EDGE Console owns
its own authenticated export and publishes only the sanitized fields needed here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from urllib.request import Request, urlopen

import psycopg2

from .console_forecast_sync import sync_console_runs

SCHEMA_VERSION = "5DR_CONSOLE_HANDOFF_V1"
MAX_HANDOFF_AGE_SECONDS = 5400


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/json", "Cache-Control": "no-cache"},
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Handoff returned HTTP {response.status} for {url}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Console handoff returned a non-object JSON payload")
    return payload


def _validate_handoff(payload: dict) -> tuple[list[dict], dict[str, dict]]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit(
            f"CONSOLE_HANDOFF_SCHEMA_MISMATCH expected={SCHEMA_VERSION} "
            f"actual={payload.get('schema_version')}"
        )
    generated = payload.get("generated_at")
    if not isinstance(generated, str) or not generated:
        raise SystemExit("CONSOLE_HANDOFF_MISSING_GENERATED_AT")
    generated_at = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    if generated_at.tzinfo is None:
        raise SystemExit("CONSOLE_HANDOFF_GENERATED_AT_NOT_TIMEZONE_AWARE")
    age = (datetime.now(timezone.utc) - generated_at.astimezone(timezone.utc)).total_seconds()
    if age < -300 or age > MAX_HANDOFF_AGE_SECONDS:
        raise SystemExit(f"CONSOLE_HANDOFF_STALE age_seconds={int(age)}")

    entries = payload.get("runs")
    if not isinstance(entries, list):
        raise SystemExit("CONSOLE_HANDOFF_RUNS_NOT_ARRAY")

    runs: list[dict] = []
    requests: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit("CONSOLE_HANDOFF_ENTRY_INVALID")
        run = entry.get("run")
        request = entry.get("request")
        if not isinstance(run, dict) or not isinstance(request, dict):
            raise SystemExit("CONSOLE_HANDOFF_ENTRY_MISSING_RUN_OR_REQUEST")
        run_id = str(run.get("run_id") or "").strip()
        if not run_id:
            raise SystemExit("CONSOLE_HANDOFF_RUN_ID_MISSING")
        if run_id in requests:
            raise SystemExit(f"CONSOLE_HANDOFF_DUPLICATE_RUN_ID {run_id}")
        runs.append(run)
        requests[run_id] = request
    return runs, requests


def main() -> int:
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    handoff_url = (os.environ.get("EDGE_CONSOLE_HANDOFF_URL") or "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if not handoff_url:
        raise SystemExit("EDGE_CONSOLE_HANDOFF_URL is required")

    payload = _get_json(handoff_url)
    runs, request_cache = _validate_handoff(payload)

    def request_fetcher(run_id: str) -> dict:
        return request_cache.get(run_id, {})

    conn = psycopg2.connect(database_url)
    try:
        summary = sync_console_runs(conn, runs, request_fetcher)
        unaccounted_complete = summary.complete_runs_seen - summary.imported - summary.already_imported
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM runs r
                  JOIN forecasts f ON f.run_id=r.run_id
                 WHERE r.notes LIKE 'EDGE_CONSOLE_RUN_ID=%'
                   AND (
                     (SELECT COUNT(*) FROM daily_forecasts df WHERE df.forecast_id=f.forecast_id) <> 5
                     OR NOT EXISTS (
                       SELECT 1 FROM forecast_governance fg WHERE fg.forecast_id=f.forecast_id
                     )
                   )
                """
            )
            broken_imports = int(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT COUNT(*)
                  FROM forecast_governance fg
                 WHERE fg.run_class='CANONICAL_CANDIDATE'
                   AND fg.validity_status='VALID'
                   AND fg.canonical_window_close <= CURRENT_TIMESTAMP
                   AND NOT EXISTS (
                     SELECT 1 FROM canonical_selections cs
                      WHERE cs.target_trading_date=fg.target_trading_date
                   )
                """
            )
            unfinalized_closed_windows = int(cur.fetchone()[0] or 0)

        if unaccounted_complete or broken_imports or unfinalized_closed_windows:
            raise SystemExit(
                "CANONICAL_SYNC_INTEGRITY_FAILED "
                f"unaccounted_complete={unaccounted_complete} "
                f"broken_imports={broken_imports} "
                f"unfinalized_closed_windows={unfinalized_closed_windows}"
            )

        print(json.dumps({
            "status": "CONSOLE_CANONICAL_SYNC_COMPLETE",
            "handoff_generated_at": payload["generated_at"],
            "summary": summary.to_dict(),
            "integrity": {
                "unaccounted_complete": unaccounted_complete,
                "broken_imports": broken_imports,
                "unfinalized_closed_windows": unfinalized_closed_windows,
            },
            "trading_enabled": False,
            "methodology_changed": False,
        }, sort_keys=True))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
