import unittest

from experiments.data_contract import DataArchitectureError
from experiments.participation_candidate import (
    HEAVYWEIGHT_SYMBOLS,
    SECTOR_INDEX_NAMES,
    SECTOR_PROVIDER_NAMES,
    resolve_candidate,
)


def equity(symbol):
    return {
        "instrument_key": f"NSE_EQ|{symbol}_KEY",
        "trading_symbol": symbol,
        "name": symbol,
        "segment": "NSE_EQ",
    }


def sector(provider_name):
    return {
        "instrument_key": f"NSE_INDEX|{provider_name}",
        "trading_symbol": provider_name,
        "name": provider_name,
        "segment": "NSE_INDEX",
    }


class ParticipationCandidateTests(unittest.TestCase):
    def records(self):
        return [equity(symbol) for symbol in HEAVYWEIGHT_SYMBOLS] + [
            sector(SECTOR_PROVIDER_NAMES[label][0]) for label in SECTOR_INDEX_NAMES
        ]

    def test_candidate_resolves_exact_provider_aliases_but_stays_unapproved(self):
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

    def test_display_label_is_not_used_as_fuzzy_provider_substitute(self):
        records = self.records()
        financial_provider_name = SECTOR_PROVIDER_NAMES["Nifty Financial Services"][0]
        records = [row for row in records if row.get("name") != financial_provider_name]
        records.append(sector("Nifty Financial Services"))
        with self.assertRaises(DataArchitectureError):
            resolve_candidate(records)


if __name__ == "__main__":
    unittest.main()
