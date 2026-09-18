import unittest

from experiments.data_contract import DataArchitectureError
from experiments.participation_universe import (
    APPROVAL_REF,
    APPROVED_HEAVYWEIGHT_KEYS,
    APPROVED_SECTOR_INDEX_KEYS,
    approved_participation_gate,
    approved_participation_universe,
    build_participation_universe,
    unresolved_participation_gate,
)


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

    def test_user_approved_v223_universe_is_exactly_8_plus_4(self):
        universe = approved_participation_universe()
        self.assertEqual(universe.approval_ref, APPROVAL_REF)
        self.assertEqual(universe.heavyweight_keys, APPROVED_HEAVYWEIGHT_KEYS)
        self.assertEqual(universe.sector_index_keys, APPROVED_SECTOR_INDEX_KEYS)
        self.assertEqual(len(universe.heavyweight_keys), 8)
        self.assertEqual(len(universe.sector_index_keys), 4)
        self.assertFalse(universe.describe()["methodology_changed"])
        self.assertFalse(universe.describe()["screening_enabled"])

    def test_approved_gate_is_ready_without_missing_variables(self):
        gate = approved_participation_gate()
        self.assertEqual(gate["status"], "READY")
        self.assertEqual(gate["approval_ref"], APPROVAL_REF)
        self.assertEqual(gate["missing_variables"], [])
        self.assertFalse(gate["screening_enabled"])
        self.assertFalse(gate["methodology_changed"])

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

    def test_unresolved_gate_remains_available_for_legacy_fail_closed_audit(self):
        gate = unresolved_participation_gate()
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertEqual(set(gate["missing_variables"]), {"NIFTY_HEAVYWEIGHTS", "NIFTY_SECTOR_INDICES"})
        self.assertFalse(gate["screening_enabled"])
        self.assertFalse(gate["methodology_changed"])


if __name__ == "__main__":
    unittest.main()
