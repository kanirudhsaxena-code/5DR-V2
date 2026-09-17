import json
from pathlib import Path
import unittest

from experiments.data_contract import DataArchitectureError
from experiments.shadow_validation import build_pair_observation, summarize_validation_series


def _result(des5=10.0, direction="RANGE", trust=70.0, edge=68.0, tradeable=False, bull=25.0, range_=50.0, bear=25.0):
    return {"des5":des5,"directional_label":direction,"market_trust":trust,"execution_edge":edge,
            "tradeable":tradeable,"probabilities":{"BULL":bull,"RANGE":range_,"BEAR":bear}}


def _record(source_mode, session_date, window, cutoff, fingerprint, request_id, result=None):
    return {"source_mode":source_mode,"session_date_ist":session_date,"comparison_window_id":window,
            "evidence_cutoff_ist":cutoff,"evidence_fingerprint":fingerprint,"request_id":request_id,
            "engine_result":result or _result()}


class ShadowValidationTests(unittest.TestCase):
    def test_same_manual_run_with_small_time_delta_is_comparable(self):
        reference = _record("SCREENSHOT_ASSISTED","2026-09-17","G11-20260917-RUN1","2026-09-17T10:02:00+05:30","a"*64,"ref-1")
        structured = _record("UPSTOX_STRUCTURED","2026-09-17","G11-20260917-RUN1","2026-09-17T10:00:00+05:30","b"*64,"struct-1",_result(des5=12.0))
        observation = build_pair_observation(reference, structured)
        self.assertEqual(observation["status"], "COMPARABLE_OBSERVATION")
        self.assertEqual(observation["pair_delta_seconds"], 120.0)
        self.assertEqual(observation["timing_quality"], "PREFERRED")

    def test_time_delta_over_five_minutes_is_observational_only(self):
        reference = _record("SCREENSHOT_ASSISTED","2026-09-17","G11-20260917-RUN1","2026-09-17T10:06:00+05:30","a"*64,"ref-1")
        structured = _record("UPSTOX_STRUCTURED","2026-09-17","G11-20260917-RUN1","2026-09-17T10:00:00+05:30","b"*64,"struct-1")
        observation = build_pair_observation(reference, structured)
        self.assertEqual(observation["status"], "OBSERVATIONAL_ONLY")
        self.assertIn("EVIDENCE_TIME_DELTA_EXCEEDS_TOLERANCE", observation["reasons"])

    def test_three_distinct_manual_runs_same_session_become_review_ready_not_pass(self):
        observations = []
        for index, minute in enumerate((0,30,60), start=1):
            hour = 10 + minute//60; mm = minute%60; window=f"G11-20260917-RUN{index}"
            reference = _record("SCREENSHOT_ASSISTED","2026-09-17",window,f"2026-09-17T{hour:02d}:{mm:02d}:45+05:30",f"{index:x}"*64,f"ref-{index}",_result(des5=10+index))
            structured = _record("UPSTOX_STRUCTURED","2026-09-17",window,f"2026-09-17T{hour:02d}:{mm:02d}:00+05:30",f"{index+8:x}"*64,f"struct-{index}",_result(des5=11+index))
            observations.append(build_pair_observation(reference, structured))
        summary = summarize_validation_series(observations, required_comparable_runs=3)
        self.assertEqual(summary["status"], "REVIEW_READY")
        self.assertEqual(summary["distinct_comparable_runs"], 3)
        self.assertEqual(summary["distinct_comparable_sessions"], 1)
        self.assertFalse(summary["acceptance_decision_made"])

    def test_duplicate_manual_run_fails_closed(self):
        ref = _record("SCREENSHOT_ASSISTED","2026-09-17","G11-20260917-RUN1","2026-09-17T10:00:20+05:30","a"*64,"ref-1")
        struct = _record("UPSTOX_STRUCTURED","2026-09-17","G11-20260917-RUN1","2026-09-17T10:00:00+05:30","b"*64,"struct-1")
        obs = build_pair_observation(ref, struct)
        with self.assertRaises(DataArchitectureError): summarize_validation_series([obs, dict(obs)], required_comparable_runs=2)

    def test_primary_series_rejects_mixed_sessions(self):
        a = build_pair_observation(_record("SCREENSHOT_ASSISTED","2026-09-17","A","2026-09-17T10:00:00+05:30","a"*64,"r1"), _record("UPSTOX_STRUCTURED","2026-09-17","A","2026-09-17T10:00:00+05:30","b"*64,"s1"))
        b = build_pair_observation(_record("SCREENSHOT_ASSISTED","2026-09-18","B","2026-09-18T10:00:00+05:30","c"*64,"r2"), _record("UPSTOX_STRUCTURED","2026-09-18","B","2026-09-18T10:00:00+05:30","d"*64,"s2"))
        with self.assertRaises(DataArchitectureError): summarize_validation_series([a,b], required_comparable_runs=2)

    def test_locked_protocol_is_three_manual_runs_one_session_plus_rollover(self):
        path = Path(__file__).resolve().parents[1] / "experiments" / "g11_validation_protocol.json"
        protocol = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(protocol["schema"], "5dr-v2-2-3-g11-validation-protocol-v2")
        self.assertEqual(protocol["required_manual_runs"], 3)
        self.assertEqual(protocol["required_distinct_sessions"], 1)
        self.assertTrue(protocol["same_session_required_for_primary_series"])
        self.assertTrue(protocol["manual_trigger_required"])
        self.assertEqual(protocol["preferred_pair_delta_seconds"], 180)
        self.assertEqual(protocol["max_pair_delta_seconds"], 300)
        self.assertTrue(protocol["next_session_rollover_required"])
        self.assertFalse(protocol["exact_same_evidence_cutoff_required"])
        self.assertFalse(protocol["production_activation_decision_automatic"])
        self.assertFalse(protocol["methodology_changed"])


if __name__ == "__main__": unittest.main()
