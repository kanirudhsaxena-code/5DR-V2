import unittest

from experiments.data_contract import DataArchitectureError
from experiments.shadow_validation import build_pair_observation, summarize_validation_series


def _result(des5=10.0, direction="RANGE", trust=70.0, edge=68.0, tradeable=False, bull=25.0, range_=50.0, bear=25.0):
    return {
        "des5": des5,
        "directional_label": direction,
        "market_trust": trust,
        "execution_edge": edge,
        "tradeable": tradeable,
        "probabilities": {"BULL": bull, "RANGE": range_, "BEAR": bear},
    }


def _record(source_mode, session_date, window, cutoff, fingerprint, request_id, result=None):
    return {
        "source_mode": source_mode,
        "session_date_ist": session_date,
        "comparison_window_id": window,
        "evidence_cutoff_ist": cutoff,
        "evidence_fingerprint": fingerprint,
        "request_id": request_id,
        "engine_result": result or _result(),
    }


class ShadowValidationTests(unittest.TestCase):
    def test_exact_pair_is_comparable_and_never_auto_accepts(self):
        reference = _record(
            "SCREENSHOT_ASSISTED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "a" * 64, "ref-1",
        )
        structured = _record(
            "UPSTOX_STRUCTURED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "b" * 64, "struct-1",
            _result(des5=12.0, trust=71.5, edge=69.0, bull=26.0, range_=49.0, bear=25.0),
        )
        observation = build_pair_observation(reference, structured)
        self.assertEqual(observation["status"], "COMPARABLE_OBSERVATION")
        self.assertTrue(observation["acceptance_eligible"])
        self.assertFalse(observation["acceptance_decision_made"])
        self.assertFalse(observation["production_activation_decision_made"])
        self.assertEqual(observation["comparison"]["des5_delta"], 2.0)
        self.assertEqual(observation["comparison"]["market_trust_delta"], 1.5)
        self.assertEqual(observation["comparison"]["probability_deltas"]["BULL"], 1.0)

    def test_temporal_mismatch_is_observational_only(self):
        reference = _record(
            "SCREENSHOT_ASSISTED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "a" * 64, "ref-1",
        )
        structured = _record(
            "UPSTOX_STRUCTURED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:31:00+05:30", "b" * 64, "struct-1",
        )
        observation = build_pair_observation(reference, structured)
        self.assertEqual(observation["status"], "OBSERVATIONAL_ONLY")
        self.assertFalse(observation["acceptance_eligible"])
        self.assertIn("EVIDENCE_CUTOFF_MISMATCH", observation["reasons"])

    def test_three_distinct_comparable_sessions_become_review_ready_not_pass(self):
        observations = []
        for index, session_date in enumerate(("2026-09-17", "2026-09-18", "2026-09-21"), start=1):
            compact = session_date.replace("-", "")
            window = f"G11-{compact}-1030"
            cutoff = f"{session_date}T10:30:00+05:30"
            reference = _record(
                "SCREENSHOT_ASSISTED", session_date, window, cutoff,
                f"{index:x}" * 64, f"ref-{index}", _result(des5=10.0 + index),
            )
            structured = _record(
                "UPSTOX_STRUCTURED", session_date, window, cutoff,
                f"{index + 8:x}" * 64, f"struct-{index}", _result(des5=11.0 + index),
            )
            observations.append(build_pair_observation(reference, structured))

        summary = summarize_validation_series(observations, required_distinct_sessions=3)
        self.assertEqual(summary["status"], "REVIEW_READY")
        self.assertEqual(summary["distinct_comparable_sessions"], 3)
        self.assertFalse(summary["acceptance_decision_made"])
        self.assertFalse(summary["production_activation_decision_made"])
        self.assertNotIn("PASS", summary["status"])

    def test_duplicate_comparable_session_fails_closed(self):
        reference = _record(
            "SCREENSHOT_ASSISTED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "a" * 64, "ref-1",
        )
        structured = _record(
            "UPSTOX_STRUCTURED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "b" * 64, "struct-1",
        )
        observation = build_pair_observation(reference, structured)
        with self.assertRaises(DataArchitectureError):
            summarize_validation_series([observation, dict(observation)], required_distinct_sessions=2)

    def test_bad_source_mode_or_fingerprint_fails_closed(self):
        reference = _record(
            "WRONG", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "a" * 64, "ref-1",
        )
        structured = _record(
            "UPSTOX_STRUCTURED", "2026-09-17", "G11-20260917-1030",
            "2026-09-17T10:30:00+05:30", "b" * 64, "struct-1",
        )
        with self.assertRaises(DataArchitectureError):
            build_pair_observation(reference, structured)
        reference["source_mode"] = "SCREENSHOT_ASSISTED"
        reference["evidence_fingerprint"] = "not-a-hash"
        with self.assertRaises(DataArchitectureError):
            build_pair_observation(reference, structured)


if __name__ == "__main__":
    unittest.main()
