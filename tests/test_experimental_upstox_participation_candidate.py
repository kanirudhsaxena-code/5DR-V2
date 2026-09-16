import unittest

from experiments.data_contract import DataArchitectureError
from experiments.participation_candidate import HEAVYWEIGHT_SYMBOLS, SECTOR_INDEX_NAMES, resolve_candidate


def equity(symbol):
    return {
        "instrument_key": f"NSE_EQ|{symbol}_KEY",
        "trading_symbol": symbol,
        "name": symbol,
        "segment": "NSE_EQ",
    }


def sector(name):
    return {
        "instrument_key": f"NSE_INDEX|{name}",
        "trading_symbol": name,
        "name": name,
        "segment": "NSE_INDEX",
    }


class ParticipationCandidateTests(unittest.TestCase):
    def records(self):
        return [equity(symbol) for symbol in HEAVYWEIGHT_SYMBOLS] + [sector(name) for name in SECTOR_INDEX_NAMES]

    def test_candidate_resolves_exact_fixed_names_but_stays_unapproved(self):
        result = resolve_candidate(self.records())
        self.assertEqual(result["status"], "PROPOSED_NOT_APPROVED")
        self.assertEqual(set(result["heavyweights"]), set(HEAVYWEIGHT_SYMBOLS))
        self.assertEqual(set(result["sectors"]), set(SECTOR_INDEX_NAMES))
        self.assertFalse(result["activation_enabled"])
        self.assertFalse(result["screening_enabled"])
        self.assertFalse(result["methodology_changed"])

    def test_missing_identity_fails_closed(self):
        records = self.records()
        records = [row for row in records if row.get("trading_symbol") != HEAVYWEIGHT_SYMBOLS[0]]
        with self.assertRaises(DataArchitectureError):
            resolve_candidate(records)

    def test_duplicate_exact_identity_fails_closed(self):
        records = self.records()
        duplicate = dict(equity(HEAVYWEIGHT_SYMBOLS[0]))
        duplicate["instrument_key"] = "NSE_EQ|OTHER_KEY"
        records.append(duplicate)
        with self.assertRaises(DataArchitectureError):
            resolve_candidate(records)

    def test_equity_cannot_resolve_from_index_segment(self):
        records = self.records()
        records = [row for row in records if row.get("trading_symbol") != HEAVYWEIGHT_SYMBOLS[0]]
        records.append(sector(HEAVYWEIGHT_SYMBOLS[0]))
        with self.assertRaises(DataArchitectureError):
            resolve_candidate(records)


if __name__ == "__main__":
    unittest.main()
