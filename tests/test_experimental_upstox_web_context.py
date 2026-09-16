import unittest

from experiments.data_contract import DataArchitectureError, build_record
from experiments.evidence_bundle import build_evidence_bundle
from experiments.web_context import (
    DEFAULT_REQUIRED_EXTERNAL_CATEGORIES,
    build_web_context_item,
    prepare_web_context,
)


def record(variable_id="NIFTY_PRICE_CANDLES"):
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
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
        source_reference="/v3/test",
        source_sha256="a" * 64,
    )


def chart():
    items = {}
    for timeframe in ("1d", "1h", "30m", "15m", "5m"):
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
        "five_minute_execution_only": True,
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
    }


def item(category, suffix):
    return build_web_context_item(
        category=category,
        source_semantic="OFFICIAL_WEB" if category == "MACRO_EVENTS_GEOPOLITICS" else "WEB_RESEARCH",
        source_reference=f"https://example.invalid/{suffix}",
        source_sha256=suffix * 64,
        authority="OFFICIAL_REGULATORY" if category == "MACRO_EVENTS_GEOPOLITICS" else "REPUTABLE_SECONDARY",
        observed_at="2026-09-16T06:00:00+00:00",
        retrieved_at="2026-09-16T06:04:00+00:00",
        fact_summary=f"Validated bounded research fact for {category}",
    )


class WebContextTests(unittest.TestCase):
    def test_required_context_is_validated_and_fact_summary_is_frozen(self):
        context = prepare_web_context(
            [
                item("DXY_RATES", "b"),
                item("MACRO_EVENTS_GEOPOLITICS", "c"),
            ],
            frozen_at="2026-09-16T06:05:00+00:00",
        )
        bundle = build_evidence_bundle(
            run_id="web-context-run",
            frozen_at="2026-09-16T06:05:00+00:00",
            quantitative_records=[record()],
            chart_evidence=chart(),
            external_evidence=context,
            required_variables={"NIFTY_PRICE_CANDLES"},
            required_external_categories=DEFAULT_REQUIRED_EXTERNAL_CATEGORIES,
        )
        self.assertEqual(bundle["status"], "READY")
        self.assertIn("fact_summary", bundle["external_evidence"][0])
        self.assertEqual(len(bundle["external_evidence"][0]["research_sha256"]), 64)

    def test_tampered_fact_summary_fails_fingerprint_validation(self):
        evidence = item("DXY_RATES", "b")
        evidence["fact_summary"] = "tampered after fingerprint"
        with self.assertRaises(DataArchitectureError):
            prepare_web_context(
                [evidence, item("MACRO_EVENTS_GEOPOLITICS", "c")],
                frozen_at="2026-09-16T06:05:00+00:00",
            )

    def test_stale_research_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            prepare_web_context(
                [item("DXY_RATES", "b"), item("MACRO_EVENTS_GEOPOLITICS", "c")],
                frozen_at="2026-09-18T06:05:00+00:00",
                max_age_seconds=86400,
            )

    def test_missing_required_category_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            prepare_web_context(
                [item("DXY_RATES", "b")],
                frozen_at="2026-09-16T06:05:00+00:00",
            )

    def test_non_https_source_is_rejected(self):
        with self.assertRaises(DataArchitectureError):
            build_web_context_item(
                category="DXY_RATES",
                source_semantic="WEB_RESEARCH",
                source_reference="http://example.invalid/not-allowed",
                source_sha256="b" * 64,
                authority="REPUTABLE_SECONDARY",
                observed_at="2026-09-16T06:00:00+00:00",
                retrieved_at="2026-09-16T06:04:00+00:00",
                fact_summary="fact",
            )


if __name__ == "__main__":
    unittest.main()
