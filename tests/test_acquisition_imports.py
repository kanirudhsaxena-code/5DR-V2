import unittest


class AcquisitionImportTests(unittest.TestCase):
    def test_modules_import(self):
        import src.autonomous_acquisition
        import src.upstox_evidence
        import src.event_evidence
        import src.source_registry
        import src.execution_risk_evidence
        import src.market_trust_evidence
        import src.acquisition_shadow_runner


if __name__ == "__main__":
    unittest.main()
