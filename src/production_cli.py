"""CLI entry point for the governed 5DR V2.2.2 lifecycle wrapper.

Consumes an already-normalized EvidencePacket JSON handoff. It does not acquire
market evidence, interpret screenshots, research the web, or place trades.
"""
from __future__ import annotations

import argparse
import json
import os

from .lifecycle_db_adapter import LifecycleDbAdapter
from .production_activation import activate


def _enabled(value: str | None) -> bool:
    return (value or '').strip().lower() == 'true'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit('DATABASE_URL is required')

    # The production driver is an execution dependency, not a dependency of the
    # deterministic framework/test modules. The Actions production wrapper installs it.
    import psycopg2

    writes_enabled = _enabled(os.environ.get('LIFECYCLE_WRITES_ENABLED'))
    db = LifecycleDbAdapter(lambda: psycopg2.connect(database_url))
    result = activate(db, args.evidence, writes_enabled=writes_enabled)
    summary = result.summary
    payload = {
        'mode': result.mode,
        'writes_enabled': result.writes_enabled,
        'evidence_file_present': result.evidence_file_present,
        'reason': result.reason,
        'summary': None if summary is None else summary.__dict__,
    }
    print(json.dumps(payload, default=str, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
