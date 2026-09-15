import unittest

from experiments.upstox_safe_diagnostics import diagnostic_code
from phase1.upstox import PipelineError


class SafeDiagnosticTests(unittest.TestCase):
    def test_known_sanitizer_failure_is_specific_but_sanitized(self):
        self.assertEqual(diagnostic_code(PipelineError("Inconsistent underlying spot across chain")), "UNDERLYING_SPOT_INCONSISTENT")
        self.assertEqual(diagnostic_code(PipelineError("CE contract not found")), "CE_CONTRACT_NOT_FOUND")

    def test_dynamic_numeric_detail_is_not_exposed(self):
        self.assertEqual(diagnostic_code(PipelineError("CE ltp negative")), "CE_LTP_INVALID")

    def test_unknown_exception_remains_generic(self):
        self.assertEqual(diagnostic_code(PipelineError("secret-looking arbitrary detail")), "DATA_VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
