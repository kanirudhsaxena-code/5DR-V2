import unittest
from datetime import datetime, timezone

from experiments.live_macro_facts import (
    FACT_EXTRACTED,
    REFERENCE_ONLY,
    extract_role_facts,
    fact_summary_prefix,
)


NOW = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)


class LiveMacroFactsTests(unittest.TestCase):
    def test_h15_extracts_release_and_latest_visible_10y_value(self):
        text = (
            "Selected Interest Rates Daily Release date: September 15, 2026 "
            "Federal funds (effective) 3.63 3.63 3.63 3.63 3.63 "
            "Treasury constant maturities Nominal 1-year 4.15 4.17 4.28 4.35 4.37 "
            "10-year 4.80 4.83 4.95 4.96 4.97 20-year 5.26 5.28 5.39 5.38 5.37"
        )
        package = extract_role_facts("RATES_REFERENCE", text, now=NOW)
        self.assertEqual(package["fact_quality"], FACT_EXTRACTED)
        self.assertEqual(package["facts"]["release_date"], "September 15, 2026")
        self.assertEqual(package["facts"]["treasury_10y_percent"], 4.97)
        self.assertEqual(package["facts"]["effective_fed_funds_percent"], 3.63)

    def test_calendar_extracts_current_month_meeting_and_decision_day(self):
        text = "2026 FOMC Meetings January 27-28 March 17-18 June 16-17 July 28-29 September 15-16* October 27-28"
        package = extract_role_facts("MACRO_CALENDAR", text, now=NOW)
        self.assertEqual(package["fact_quality"], FACT_EXTRACTED)
        self.assertEqual(package["facts"]["meeting_start_date"], "2026-09-15")
        self.assertEqual(package["facts"]["meeting_end_date"], "2026-09-16")
        self.assertTrue(package["facts"]["decision_day_matches_retrieval_date"])

    def test_rbi_extracts_policy_rate_and_source_dated_fx(self):
        text = (
            "Current Rates Policy Rates Policy Repo Rate : 5.25% Standing Deposit Facility Rate : 5.00% "
            "Exchange Rates INR / 1 USD : 95.2560 (As at 1.00pm of August 10, 2026)"
        )
        package = extract_role_facts("INDIA_POLICY", text, now=NOW)
        self.assertEqual(package["fact_quality"], FACT_EXTRACTED)
        self.assertEqual(package["facts"]["policy_repo_rate_percent"], 5.25)
        self.assertEqual(package["facts"]["rbi_displayed_usdinr"], 95.256)
        self.assertEqual(package["facts"]["rbi_displayed_usdinr_as_at"], "August 10, 2026")

    def test_non_numeric_reference_is_explicitly_reference_only(self):
        package = extract_role_facts("DXY_OWNER_REFERENCE", "U.S. Dollar Index methodology only", now=NOW)
        self.assertEqual(package["fact_quality"], REFERENCE_ONLY)
        self.assertEqual(package["facts"], {})
        prefix = fact_summary_prefix("DXY_OWNER_REFERENCE", package)
        self.assertIn("fact_quality=REFERENCE_ONLY", prefix)
        self.assertIn("facts_json={}", prefix)


if __name__ == "__main__":
    unittest.main()
