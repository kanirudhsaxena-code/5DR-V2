import unittest
from pathlib import Path

class ForecastReleaseGuardTests(unittest.TestCase):
    def test_no_release_true_literal_in_acquisition_code(self):
        text = "\n".join(Path(p).read_text() for p in Path("src").glob("*acquisition*.py"))
        self.assertNotIn('"forecast_release_enabled": True', text)

if __name__ == "__main__":
    unittest.main()
