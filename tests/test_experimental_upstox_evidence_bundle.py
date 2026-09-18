import unittest
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.evidence_bundle import build_evidence_bundle


def record(variable_id, *, semantic="UPSTOX_AUTHENTICATED", suffix="a"):
    return build_record(
        provider_id="UPSTOX",
        source_semantic=semantic,
        variable_id=variable_id,
        consumer="5DR",
        subject={
            "kind": "MARKET_INSTRUMENT",
            "id": "NIFTY50",
            "name": "NIFTY 50",
            "exchange": "NSE",
            "instrument_key": "NSE_INDEX|Nifty 50",
        },
        metric="TEST",
        values={"value": 1},
        timeframe="1h",
        provider_timestamp="2026-09-16T06:00:00+00:00",
        acquisition_timestamp="2026-09-16T06:00:05+00:00",
        freshness_status="LIVE",
        source_reference="/v3/test/" + suffix,
        source_sha256=(suffix * 64)[:64],
    )


def chart(timeframes=("1d", "1h", "30m", "15m", "5m")):
    items = {}
    for timeframe in timeframes:
        items[timeframe] = {
            "schema": "5dr-derived-chart-evidence-v1",
            "timeframe": timeframe,
            "directional_score_assigned": False,
            "forecast_released": False,
            "trading_enabled": False,
        }
    return {
        "schema": "5dr-multi-timeframe-chart-evidence-v1",
        "timeframes": items,
        "directional_alignment_excluding_5m": "MIXED",
        "five_minute_execution_only": "5m" in items,
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
    }


class EvidenceBundleTests(unittest.TestCase):
    def test_complete_snapshot_can_be_frozen_without_screenshot_dependency(self):
        bundle = build_evidence_bundle(
            run_id="run-1",
            frozen_at=datetime(2026, 9, 16, 6, 5, tzinfo=timezone.utc),
            quantitative_records=[
                record("NIFTY_PRICE_CANDLES", suffix="a"),
                record("INDIA_VIX", suffix="b"),
            ],
            chart_evidence=chart(),
            required_variables={"NIFTY_PRICE_CANDLES", "INDIA_VIX"},
        )
        self.assertEqual(bundle["status"], "READY")
        self.assertFalse(bundle["screenshot_policy"]["screenshot_dependency"])
        self.assertEqual(len(bundle["bundle_sha256"]), 64)
        self.assertFalse(bundle["directional_score_assigned"])
        self.assertFalse(bundle["production_5dr_write_enabled"])

    def test_missing_machine_variable_blocks_bundle(self):
        bundle = build_evidence_bundle(
            run_id="run-2",
            frozen_at="2026-09-16T06:05:00+00:00",
            quantitative_records=[record("NIFTY_PRICE_CANDLES")],
            chart_evidence=chart(),
            required_variables={"NIFTY_PRICE_CANDLES", "NIFTY_FUTURES"},
        )
        self.assertEqual(bundle["status"], "BLOCKED")
        self.assertIn("MISSING_QUANTITATIVE_VARIABLES", bundle["blocked_reasons"])
        self.assertEqual(bundle["coverage"]["missing_variables"], ["NIFTY_FUTURES"])

    def test_missing_core_chart_timeframe_blocks_bundle(self):
        bundle = build_evidence_bundle(
            run_id="run-3",
            frozen_at="2026-09-16T06:05:00+00:00",
            quantitative_records=[record("NIFTY_PRICE_CANDLES")],
            chart_evidence=chart(("1d", "1h", "15m")),
            required_variables={"NIFTY_PRICE_CANDLES"},
        )
        self.assertEqual(bundle["status"], "BLOCKED")
        self.assertEqual(bundle["coverage"]["missing_chart_timeframes"], ["30m"])

    def test_required_web_context_is_explicit_not_faked_as_machine_data(self):
        bundle = build_evidence_bundle(
            run_id="run-4",
            frozen_at="2026-09-16T06:05:00+00:00",
            quantitative_records=[record("NIFTY_PRICE_CANDLES")],
            chart_evidence=chart(),
            required_variables={"NIFTY_PRICE_CANDLES"},
            required_external_categories={"MACRO_EVENTS_GEOPOLITICS"},
            external_evidence=[{
                "category": "MACRO_EVENTS_GEOPOLITICS",
                "source_semantic": "OFFICIAL_WEB",
                "source_reference": "https://example.invalid/official-event",
                "source_sha256": "c" * 64,
                "retrieved_at": "2026-09-16T06:04:00+00:00",
                "validation_status": "VALID",
            }],
        )
        self.assertEqual(bundle["status"], "READY")
        self.assertEqual(bundle["external_evidence"][0]["source_semantic"], "OFFICIAL_WEB")

    def test_missing_required_web_context_blocks_release_boundary(self):
        bundle = build_evidence_bundle(
            run_id="run-5",
            frozen_at="2026-09-16T06:05:00+00:00",
            quantitative_records=[record("NIFTY_PRICE_CANDLES")],
            chart_evidence=chart(),
            required_variables={"NIFTY_PRICE_CANDLES"},
            required_external_categories={"MACRO_EVENTS_GEOPOLITICS"},
        )
        self.assertEqual(bundle["status"], "BLOCKED")
        self.assertIn("MISSING_EXTERNAL_CONTEXT", bundle["blocked_reasons"])

    def test_duplicate_quantitative_fingerprint_fails_closed(self):
        same = record("NIFTY_PRICE_CANDLES")
        with self.assertRaises(DataArchitectureError):
            build_evidence_bundle(
                run_id="run-6",
                frozen_at="2026-09-16T06:05:00+00:00",
                quantitative_records=[same, same],
                chart_evidence=chart(),
                required_variables={"NIFTY_PRICE_CANDLES"},
            )

    def test_non_5dr_or_ineligible_record_fails_closed(self):
        bad = record("NIFTY_PRICE_CANDLES")
        bad["eligible_for_consumer"] = False
        with self.assertRaises(DataArchitectureError):
            build_evidence_bundle(
                run_id="run-7",
                frozen_at="2026-09-16T06:05:00+00:00",
                quantitative_records=[bad],
                chart_evidence=chart(),
                required_variables={"NIFTY_PRICE_CANDLES"},
            )


if __name__ == "__main__":
    unittest.main()
