from __future__ import annotations

import unittest

from prepdrill_content.runtime import Phase2Evaluator


class Phase2EvaluatorTests(unittest.TestCase):
    def test_evaluator_passes_all_adversarial_invariants(self) -> None:
        report = Phase2Evaluator().run()
        self.assertTrue(report.passed, [item.code for item in report.findings])
        self.assertGreaterEqual(report.metrics["checks_run"], 10)
        self.assertEqual(report.metrics["unpublished_leaks"], 0)
        self.assertEqual(report.metrics["duplicate_attempts"], 0)
        self.assertEqual(report.metrics["selection_determinism"], 1.0)
        self.assertGreaterEqual(report.metrics["target_precision"], 0.8)
        self.assertEqual(report.metrics["grounded_explanation_rate"], 1.0)
        self.assertTrue(report.metrics["stale_authorization_locked"])


if __name__ == "__main__":
    unittest.main()
