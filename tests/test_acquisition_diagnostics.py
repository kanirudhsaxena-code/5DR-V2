import unittest
from src.acquisition_diagnostics import bounded_diagnostic


class AcquisitionDiagnosticTests(unittest.TestCase):
    def test_known_code_preserved(self):
        self.assertEqual(bounded_diagnostic("AUTH_REJECTED"), "AUTH_REJECTED")

    def test_arbitrary_provider_error_is_not_exposed(self):
        self.assertEqual(bounded_diagnostic("secret raw provider response"), "ACQUISITION_GOVERNANCE_BLOCKED")


if __name__ == "__main__":
    unittest.main()
