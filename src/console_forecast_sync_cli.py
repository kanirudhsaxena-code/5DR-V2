"""Synchronize complete published EDGE Console 5DR runs into canonical persistence."""
from __future__ import annotations

import json
import os
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import psycopg2

from .console_forecast_sync import sync_console_runs


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Cache-Control": "no-cache"}
    client_id = (os.environ.get("CF_ACCESS_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("CF_ACCESS_CLIENT_SECRET") or "").strip()
    if client_id and client_secret:
        headers["CF-Access-Client-Id"] = client_id
        headers["CF-Access-Client-Secret"] = client_secret
    return headers


def _get_json(url: str) -> dict:
    request = Request(url, headers=_headers(), method="GET")
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Console API returned HTTP {response.status} for {url}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Console API returned a non-object JSON payload")
    return payload


def main() -> int:
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    console_url = (os.environ.get("EDGE_CONSOLE_URL") or "").strip().rstrip("/")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if not console_url:
        raise SystemExit("EDGE_CONSOLE_URL is required")

    runs_payload = _get_json(console_url + "/api/runs/latest?" + urlencode({"engine": "5DR"}))
    runs = runs_payload.get("runs")
    if not isinstance(runs, list):
        raise SystemExit("Console runs endpoint did not return a runs array")

    request_cache: dict[str, dict] = {}

    def request_fetcher(run_id: str) -> dict:
        if run_id not in request_cache:
            payload = _get_json(
                console_url + "/api/5dr/run-request?" + urlencode({"run_id": run_id})
            )
            request = payload.get("request")
            request_cache[run_id] = request if isinstance(request, dict) else {}
        return request_cache[run_id]

    conn = psycopg2.connect(database_url)
    try:
        summary = sync_console_runs(conn, runs, request_fetcher)
        print(json.dumps({
            "status": "CONSOLE_CANONICAL_SYNC_COMPLETE",
            "summary": summary.to_dict(),
            "trading_enabled": False,
            "methodology_changed": False,
        }, sort_keys=True))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
