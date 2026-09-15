import subprocess
import unittest


class NoFrameworkChangeTests(unittest.TestCase):
    def test_issue11_branch_does_not_modify_framework_semantics(self):
        """Protect mathematical/governance semantics while allowing governed adapters.

        composed_engine/orchestrator/runner are execution-layer composition files and may
        change under an explicitly governed integration PR. Scoring, trust, probability,
        execution thresholds, governance, assessment and lifecycle semantics remain frozen.
        """
        changed = subprocess.check_output(["git", "diff", "--name-only", "origin/main...HEAD"], text=True).splitlines()
        forbidden = {
            "src/scoring.py", "src/market_trust.py", "src/probability.py", "src/execution.py",
            "src/governance.py", "src/assessment.py", "src/lifecycle_executor.py",
        }
        self.assertFalse(forbidden.intersection(changed), f"Framework semantics modified: {sorted(forbidden.intersection(changed))}")


if __name__ == "__main__":
    unittest.main()
