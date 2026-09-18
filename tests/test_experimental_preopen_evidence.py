import unittest
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.preopen_evidence import (
    build_preopen_evidence_bundle,
    verify_preopen_evidence_bundle,
)

TARGET = "2026-09-18"
PREVIOUS = "2026-09-17"
FREEZE = datetime(2026, 9, 18, 3, 20, tzinfo=timezone.utc)
SUBJECT = {
    "kind": "MARKET_INSTRUMENT",
    "id": "NIFTY50",
    "name": "NIFTY 50",
}


def record(variable_id, *, freshness="LIVE", provider_ts="2026-09-18T03:15:00+00:00",
           acquired="2026-09-18T03:19:00+00:00", values=None, suffix="a"):
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id=variable_id,
        consumer="5DR",
        subject=SUBJECT,
        metric="TEST",
        values=values or {"value": 1},
        timeframe="quote",
        provider_timestamp=provider_ts,
        acquisition_timestamp=acquired,
        freshness_status=freshness,
        source_reference="/v3/test",
        source_sha256=(suffix * 64)[:64],
    )


def prior_close():
    return record(
        "NIFTY_PRICE_CANDLES",
        freshness="SESSION_FINAL",
        provider_ts="2026-09-17T10:00:00+00:00",
        acquired="2026-09-17T10:01:00+00:00",
        values={"close": 25000.0},
        suffix="b",
    )


def external(category, suffix):
    return {
        "category": category,
        "source_semantic": "OFFICIAL_WEB",
        "source_reference": "https://example.invalid/" + category.lower(),
        "source_sha256": suffix * 64,
        "retrieved_at": "2026-09-18T03:18:00+00:00",
        "validation_status": "VALID",
    }


def build(**overrides):
    args = dict(
        target_session_date=TARGET,
        previous_session_date=PREVIOUS,
        frozen_at=FREEZE,
        prior_close_record=prior_close(),
        overnight_records=[
            record("GLOBAL_RISK_INDICES", suffix="c"),
            record("CRUDE_USDINR", suffix="d"),
        ],
        external_evidence=[
            external("DXY_RATES", "e"),
            external("MACRO_EVENTS_GEOPOLITICS", "f"),
        ],
        active_expiry="2026-09-22",
        run_id="PREOPEN-20260918",
    )
    args.update(overrides)
    return build_preopen_evidence_bundle(**args)


class PreopenEvidenceTests(unittest.TestCase):
    def test_complete_preopen_bundle_is_ready_and_side_effect_free(self):
        bundle = build()
        self.assertEqual(bundle["status"], "READY")
        self.assertEqual(bundle["run_key"], "5DR:2026-09-18:PREOPEN")
        self.assertFalse(bundle["side_effects"]["forecast_release_enabled"])
        self.assertFalse(bundle["side_effects"]["trading_enabled"])
        verified = verify_preopen_evidence_bundle(bundle)
        self.assertEqual(verified["bundle_sha256"], bundle["bundle_sha256"])

    def test_stale_prior_session_close_rejected(self):
        bad = prior_close()
        bad["provider_timestamp"] = "2026-09-16T10:00:00+00:00"
        with self.assertRaises(DataArchitectureError):
            build(prior_close_record=bad)

    def test_prior_close_must_be_session_final(self):
        bad = prior_close()
        bad["freshness_status"] = "HISTORICAL"
        with self.assertRaises(DataArchitectureError):
            build(prior_close_record=bad)

    def test_target_date_binding_rejects_wrong_freeze_date(self):
        with self.assertRaises(DataArchitectureError):
            build(frozen_at=datetime(2026, 9, 17, 23, 0, tzinfo=timezone.utc))

    def test_stale_overnight_market_rejected(self):
        stale = record(
            "GLOBAL_RISK_INDICES",
            acquired="2026-09-18T02:00:00+00:00",
            provider_ts="2026-09-18T01:59:00+00:00",
            suffix="c",
        )
        with self.assertRaises(DataArchitectureError):
            build(overnight_records=[stale, record("CRUDE_USDINR", suffix="d")])

    def test_missing_overnight_market_rejected(self):
        with self.assertRaises(DataArchitectureError):
            build(overnight_records=[record("GLOBAL_RISK_INDICES", suffix="c")])

    def test_missing_dxy_or_macro_context_rejected(self):
        with self.assertRaises(DataArchitectureError):
            build(external_evidence=[external("DXY_RATES", "e")])

    def test_expired_derivative_identity_rejected(self):
        with self.assertRaises(DataArchitectureError):
            build(active_expiry="2026-09-17")

    def test_duplicate_run_rejected(self):
        with self.assertRaises(DataArchitectureError):
            build(completed_run_keys={"5DR:2026-09-18:PREOPEN"})

    def test_cross_consumer_contamination_rejected(self):
        bad = record("GLOBAL_RISK_INDICES", suffix="c")
        bad["consumer"] = "EDGE_STOCK"
        with self.assertRaises(DataArchitectureError):
            build(overnight_records=[bad, record("CRUDE_USDINR", suffix="d")])

    def test_tamper_detection(self):
        bundle = build()
        bundle["active_derivative_expiry"] = "2026-09-29"
        with self.assertRaises(DataArchitectureError):
            verify_preopen_evidence_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
