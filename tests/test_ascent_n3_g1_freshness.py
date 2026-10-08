import unittest
from datetime import date
from experiments.ascent_n3_g1_probe import NIFTY, ProbeError
from experiments.ascent_n3_g1_freshness import parsed_quote, choose_nearest_ce_pe

class FreshnessContractTests(unittest.TestCase):
    def test_timestamp_and_price_provenance(self):
        data={"NSE_INDEX:Nifty 50":{"instrument_token":NIFTY,"timestamp":"2026-10-08T15:30:00+05:30",
                                     "last_price":22231.8,"ohlc":{"ts":1791453600000}}}
        q=parsed_quote(data)
        self.assertEqual(q["last_price"],22231.8)
        self.assertIn("2026-10-08",q["provider_timestamp"])

    def test_reject_missing_quote_time(self):
        with self.assertRaisesRegex(ProbeError,"FULL_QUOTE_NO_PROVIDER_TIME"):
            parsed_quote({"NSE_INDEX:Nifty 50":{"instrument_token":NIFTY,"last_price":22231.8}})

    def test_reject_wrong_index(self):
        with self.assertRaisesRegex(ProbeError,"FULL_QUOTE_NIFTY_IDENTITY"):
            parsed_quote({"NSE_INDEX:Nifty 50":{"instrument_token":"NSE_INDEX|Bank Nifty",
                                                 "last_price":22231.8,"timestamp":"2026-10-08T15:30:00+05:30"}})

    def test_choose_ce_pe_same_expiry(self):
        rows=[]
        for expiry in ("2026-10-13","2026-10-20"):
            for side in ("CE","PE"):
                for strike in (22200.,22300.):
                    rows.append({"underlying_key":NIFTY,"expiry":expiry,"instrument_type":side,
                                 "strike_price":strike,"lot_size":65,"instrument_key":f"NSE_FO|123{side}|{expiry}|{strike}"})
        pair=choose_nearest_ce_pe(rows,22231.8,date(2026,10,8))
        self.assertEqual(pair["CE"]["expiry"],"2026-10-13")
        self.assertEqual(pair["PE"]["strike_price"],22200.)

    def test_reject_no_current_expiry(self):
        rows=[{"underlying_key":NIFTY,"expiry":"2026-10-01","instrument_type":side,
               "strike_price":22200.,"lot_size":65,"instrument_key":f"NSE_FO|123{side}"}
              for side in ("CE","PE")]
        with self.assertRaisesRegex(ProbeError,"NO_CURRENT_EXPIRY"):
            choose_nearest_ce_pe(rows,22231.8,date(2026,10,8))

if __name__=="__main__":
    unittest.main()
