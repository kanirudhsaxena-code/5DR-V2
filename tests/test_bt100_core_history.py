import unittest
from datetime import date

from bt100.run_core_history_backfill import _ranges


class Bt100CoreHistoryTests(unittest.TestCase):
    def test_short_interval_chunks_cover_continuous_window(self):
        chunks=_ranges(date(2026,5,6),date(2026,10,1),30,"minutes",5)
        self.assertGreater(len(chunks),1)
        self.assertEqual(chunks[0]["start"].isoformat(),"2026-04-06")
        self.assertEqual(chunks[-1]["end"].isoformat(),"2026-10-01")
        for left,right in zip(chunks,chunks[1:]):
            self.assertEqual((right["start"]-left["end"]).days,1)


if __name__=="__main__":
    unittest.main()
