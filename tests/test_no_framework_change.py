import subprocess
import unittest


class NoFrameworkChangeTests(unittest.TestCase):
    def test_issue11_branch_does_not_modify_core_framework_files(self):
        changed = subprocess.check_output(["git", "diff", "--name-only", "origin/main...HEAD"], text=True).splitlines()
        forbidden = {
            "src/scoring.py", "src/market_trust.py", "src/probability.py", "src/execution.py",
            "src/governance.py", "src/assessment.py", "src/lifecycle_executor.py",
            "src/runner.py", "src/composed_engine.py",
        }
        self.assertFalse(forbidden.intersection(changed), f"Issue #11 modified framework files: {sorted(forbidden.intersection(changed))}")


if __name__ == "__main__":
    unittest.main()
