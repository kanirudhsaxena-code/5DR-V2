import unittest

from experiments.data_contract import DataArchitectureError
from experiments.participation_universe import build_participation_universe, unresolved_participation_gate


class ParticipationUniverseTests(unittest.TestCase):
    def test_exact_approved_universe_is_descriptive_only(self):
        universe = build_participation_universe(
            heavyweight_keys=("NSE_EQ|A", "NSE_EQ|B"),
            sector_index_keys=("NSE_INDEX|S1", "NSE_INDEX|S2"),
            approval_ref="test-approval",
        )
        self.assertEqual(universe.heavyweight_keys, ("NSE_EQ|A", "NSE_EQ|B"))
        self.assertEqual(universe.sector_index_keys, ("NSE_INDEX|S1", "NSE_INDEX|S2"))
        self.assertFalse(universe.describe()["screening_enabled"])
        self.assertFalse(universe.describe()["methodology_changed"])

    def test_missing_approval_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            build_participation_universe(
                heavyweight_keys=("NSE_EQ|A",),
                sector_index_keys=("NSE_INDEX|S1",),
                approval_ref="",
            )

    def test_wrong_segments_fail_closed(self):
        with self.assertRaises(DataArchitectureError):
            build_participation_universe(
                heavyweight_keys=("NSE_INDEX|Nifty 50",),
                sector_index_keys=("NSE_INDEX|S1",),
                approval_ref="approved",
            )

    def test_unresolved_gate_names_only_required_missing_participation_variables(self):
        gate = unresolved_participation_gate()
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertEqual(set(gate["missing_variables"]), {"NIFTY_HEAVYWEIGHTS", "NIFTY_SECTOR_INDICES"})
        self.assertFalse(gate["screening_enabled"])
        self.assertFalse(gate["methodology_changed"])


if __name__ == "__main__":
    unittest.main()
