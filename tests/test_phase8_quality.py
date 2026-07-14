from __future__ import annotations

import unittest

from prepdrill_content.phase8 import AccessController, BackupManager, LogSanitizer, Phase8Evaluator, ReliabilityEvaluator, SecurityRepository


class Phase8QualityTests(unittest.TestCase):
    def test_access_and_logs_fail_closed(self) -> None:
        access = AccessController()
        self.assertTrue(access.allowed(role="learner", action="learner.read", actor_id="u", owner_id="u"))
        self.assertFalse(access.allowed(role="learner", action="learner.read", actor_id="u", owner_id="other"))
        clean = LogSanitizer().sanitize({"token": "secret", "message": "Bearer abc", "correct_option_id": "A"})
        self.assertEqual(clean["token"], "[REDACTED]")
        self.assertNotIn("abc", clean["message"])

    def test_replay_and_collision(self) -> None:
        repo = SecurityRepository.open()
        self.assertEqual(repo.accept_mutation(scope="x", actor_id="u", idempotency_key="k", payload={"a": 1}, epoch=1), "accepted")
        self.assertEqual(repo.accept_mutation(scope="x", actor_id="u", idempotency_key="k", payload={"a": 1}, epoch=2), "duplicate")
        with self.assertRaises(ValueError):
            repo.accept_mutation(scope="x", actor_id="u", idempotency_key="k", payload={"a": 2}, epoch=3)

    def test_restore_and_budget(self) -> None:
        manager = BackupManager(); backup = manager.create({"x": [1, 2]})
        self.assertEqual(manager.restore(backup), {"x": [1, 2]})
        self.assertTrue(ReliabilityEvaluator().evaluate([100] * 100, 0, 100)["passed"])

    def test_evaluator(self) -> None:
        report = Phase8Evaluator().run()
        self.assertTrue(report.passed, report.to_dict())
        self.assertGreaterEqual(len(report.checks), 14)


if __name__ == "__main__":
    unittest.main()
