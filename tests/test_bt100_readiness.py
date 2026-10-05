import copy
import json
import unittest
from pathlib import Path

from bt100.readiness import ReadinessError, build_report, validate_config, validate_target_dates

ROOT = Path(__file__).resolve().parents[1]


class Bt100ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "bt100/config/readiness_v0.json").read_text())
        self.evidence = json.loads((ROOT / "bt100/evidence_requirements.json").read_text())

    def test_safety_invariants_are_locked(self):
        self.assertTrue(validate_config(self.config))
        self.assertEqual(self.config["run_role"], "REPLAY")
        self.assertFalse(self.config["official_efficacy_eligible"])
        self.assertEqual(self.config["production_neuron_budget"], 0)
        self.assertFalse(self.config["production_writes_allowed"])
        self.assertFalse(self.config["trading_allowed"])
        self.assertFalse(self.config["methodology_tuning_allowed"])

    def test_nonzero_neuron_budget_fails_closed(self):
        config = copy.deepcopy(self.config)
        config["production_neuron_budget"] = 1
        with self.assertRaises(ReadinessError):
            validate_config(config)

    def test_official_efficacy_replay_is_rejected(self):
        config = copy.deepcopy(self.config)
        config["official_efficacy_eligible"] = True
        with self.assertRaises(ReadinessError):
            validate_config(config)

    def test_formal_run_stays_blocked_until_data_certified(self):
        report = build_report(self.config, self.evidence)
        self.assertFalse(report["formal_replay_ready"])
        self.assertTrue(report["g5_1_passed"])
        self.assertTrue(report["baseline_frozen"])
        self.assertFalse(report["target_dates_valid"])
        self.assertEqual(report["phase"], "READINESS_IN_PROGRESS")

    def test_exactly_100_unique_target_dates_required(self):
        sessions = []
        for i in range(100):
            target = f"2026-01-{(i % 28) + 1:02d}"
            sessions.append({
                "target_date": f"{i:03d}-{target}",
                "horizon_dates": {
                    "D+1": f"{i:03d}-{target}",
                    "D+2": f"{i:03d}-d2",
                    "D+3": f"{i:03d}-d3",
                    "D+4": f"{i:03d}-d4",
                    "D+5": f"{i:03d}-d5",
                },
            })
        self.assertEqual(len(validate_target_dates({"sessions": sessions})), 100)
        with self.assertRaises(ReadinessError):
            validate_target_dates({"sessions": sessions[:-1]})


if __name__ == "__main__":
    unittest.main()
