import unittest
from pathlib import Path


class Issue11SafetyTests(unittest.TestCase):
    def test_new_acquisition_modules_do_not_enable_trading_or_release(self):
        paths = [
            "src/autonomous_acquisition.py",
            "src/upstox_evidence.py",
            "src/event_evidence.py",
            "src/source_registry.py",
            "src/acquisition_shadow_runner.py",
        ]
        combined = "\n".join(Path(p).read_text() for p in paths)
        self.assertNotIn("trading_enabled=True", combined)
        self.assertNotIn('"trading_enabled": True', combined)
        self.assertNotIn("forecast_release_enabled=True", combined)
        self.assertNotIn('"forecast_release_enabled": True', combined)


if __name__ == "__main__":
    unittest.main()
