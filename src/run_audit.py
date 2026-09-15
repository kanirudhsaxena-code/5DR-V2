"""Durable, secret-free audit envelopes for V2.2.2 lifecycle runs."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .production_lifecycle_runner import RunSummary


def audit_dict(summary: RunSummary) -> dict:
    data = asdict(summary)
    data['started_at'] = summary.started_at.isoformat()
    data['finished_at'] = summary.finished_at.isoformat()
    data['items'] = [asdict(item) for item in summary.items]
    return data


def write_audit(summary: RunSummary, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(audit_dict(summary), indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return target
