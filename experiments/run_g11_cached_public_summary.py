"""Emit a bounded public summary from one exact cached G11 evidence bundle.

This reads the immutable cached bundle produced by a manual G11 run. It performs no
network acquisition, no forecast release, no persistence and no trading. Only public
market values needed for screenshot comparison are printed/written; source content and
secrets are never emitted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from experiments.data_contract import DataArchitectureError

BUNDLE_PATH = Path('.shadow/g11_capture/bundle.json')
CAPTURE_PATH = Path('.shadow/g11_capture/capture.json')
SUMMARY_PATH = Path(os.environ.get(
    'G11_PUBLIC_SUMMARY_PATH',
    '.shadow/g11_capture/public_summary.json',
))


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError) as exc:
        raise DataArchitectureError(f'cached G11 file unavailable: {path.name}') from exc


def _recompute_bundle_sha(bundle):
    base = dict(bundle)
    digest = str(base.pop('bundle_sha256', '')).lower()
    calculated = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(',', ':'), default=str).encode()
    ).hexdigest()
    if digest != calculated:
        raise DataArchitectureError('cached G11 bundle digest mismatch')
    return digest


def _by_variable(bundle):
    records = bundle.get('quantitative_records')
    if not isinstance(records, list):
        raise DataArchitectureError('cached G11 quantitative records missing')
    result = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get('variable_id'), str):
            result[record['variable_id']] = record
    return result


def _side_summary(leg):
    return {
        'last_price': leg.get('last_price'),
        'open_interest': leg.get('open_interest'),
        'previous_open_interest': leg.get('previous_open_interest'),
        'iv': leg.get('iv'),
        'bid_price': leg.get('bid_price'),
        'ask_price': leg.get('ask_price'),
        'bid_ask_spread': leg.get('bid_ask_spread'),
        'provider_timestamp': leg.get('timestamp'),
    }


def run():
    bundle = _load(BUNDLE_PATH)
    capture = _load(CAPTURE_PATH)
    digest = _recompute_bundle_sha(bundle)
    expected_sha = os.environ.get('EXPECTED_BUNDLE_SHA', '').strip().lower()
    expected_run = os.environ.get('EXPECTED_MANUAL_RUN_ID', '').strip()
    if expected_sha and digest != expected_sha:
        raise DataArchitectureError('cached G11 bundle is not requested bundle')
    if expected_run and capture.get('manual_run_id') != expected_run:
        raise DataArchitectureError('cached G11 capture is not requested run')
    if capture.get('bundle_sha256') != digest:
        raise DataArchitectureError('capture/bundle digest mismatch')

    q = _by_variable(bundle)
    price = q.get('NIFTY_PRICE_CANDLES', {}).get('values', {})
    futures = q.get('NIFTY_FUTURES', {}).get('values', {})
    option = q.get('NIFTY_OPTION_CHAIN', {}).get('values', {})
    vix = q.get('INDIA_VIX', {}).get('values', {})
    strikes = []
    for row in option.get('sample_strikes', []):
        if not isinstance(row, dict):
            continue
        strikes.append({
            'strike': row.get('strike'),
            'CE': _side_summary(row.get('CE', {})),
            'PE': _side_summary(row.get('PE', {})),
        })

    # Frozen evidence bundles store the validated multi-timeframe chart layer under
    # derived_chart_evidence. Retain the legacy fallback only for older experiment
    # fixtures; this changes validation observability, not 5DR methodology.
    chart = bundle.get('derived_chart_evidence') or bundle.get('chart_evidence', {})
    tf_summary = {}
    for tf, item in (chart.get('timeframes') or {}).items():
        if not isinstance(item, dict):
            continue
        trend = item.get('trend_structure') or {}
        range_event = item.get('range_event') or {}
        tf_summary[tf] = {
            'latest_timestamp': item.get('latest_timestamp'),
            'latest_close': item.get('latest_close'),
            'trend_structure': trend.get('state'),
            'high_sequence': trend.get('high_sequence'),
            'low_sequence': trend.get('low_sequence'),
            'latest_swing_highs': item.get('latest_swing_highs'),
            'latest_swing_lows': item.get('latest_swing_lows'),
            'prior_range_high': range_event.get('prior_range_high'),
            'prior_range_low': range_event.get('prior_range_low'),
            'close_state': range_event.get('close_state'),
            'liquidity_sweep': range_event.get('liquidity_sweep'),
            'failed_breakout': item.get('failed_breakout'),
            'recent_gaps': item.get('recent_gaps'),
            'execution_only': item.get('execution_only'),
        }

    runtime = bundle.get('runtime_context', {})
    result = {
        'status': 'G11_CACHED_PUBLIC_SUMMARY_READY',
        'manual_run_id': capture.get('manual_run_id'),
        'evidence_cutoff_ist': capture.get('evidence_cutoff_ist'),
        'bundle_frozen_at_ist': capture.get('bundle_frozen_at_ist'),
        'bundle_sha256': digest,
        'bundle_status': bundle.get('status'),
        'spot': price.get('spot'),
        'latest_by_timeframe': price.get('latest_by_timeframe'),
        'future': futures.get('future'),
        'future_basis_points': futures.get('basis_points'),
        'future_basis_pct_of_spot': futures.get('basis_pct_of_spot'),
        'india_vix': vix,
        'selected_expiry': option.get('selected_expiry'),
        'option_underlying_spot_price': option.get('underlying_spot_price'),
        'option_sample_strikes': strikes,
        'chart_alignment_excluding_5m': chart.get('directional_alignment_excluding_5m'),
        'chart_timeframes': tf_summary,
        'screenshot_required': runtime.get('screenshot_required'),
        'forecast_release_enabled': runtime.get('forecast_release_enabled'),
        'production_5dr_write_enabled': runtime.get('production_5dr_write_enabled'),
        'lifecycle_write_enabled': runtime.get('lifecycle_write_enabled'),
        'trading_enabled': runtime.get('trading_enabled'),
    }
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':'))
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(encoded + '\n', encoding='utf-8')
    print(encoded)
    return result


if __name__ == '__main__':
    run()
