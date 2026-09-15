import unittest
from pathlib import Path


class NoTradeApiTests(unittest.TestCase):
    def test_acquisition_modules_have_no_order_endpoints(self):
        paths = ["src/autonomous_acquisition.py", "src/upstox_evidence.py", "src/source_registry.py", "src/acquisition_shadow_runner.py"]
        text = "\n".join(Path(p).read_text().lower() for p in paths)
        for forbidden in ("place_order", "/order/place", "modify_order", "cancel_order"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
