import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation


class UnknownCategoryTests(unittest.TestCase):
    def test_unknown_category_rejected(self):
        item = SourceObservation("USER_SUPPLIED_MAGIC", "source:x", datetime.now(timezone.utc).isoformat())
        with self.assertRaisesRegex(AcquisitionBlocked, "UNKNOWN_CATEGORY"):
            item.validate(datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
