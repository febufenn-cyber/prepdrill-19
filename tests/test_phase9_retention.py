from __future__ import annotations

import unittest

from prepdrill_content.phase9 import CommunicationRepository, LearningActivity, LearningContinuity, MessageRequest, Phase9Evaluator, Preference


class Phase9RetentionTests(unittest.TestCase):
    def test_streak_and_report_use_meaningful_activity(self) -> None:
        activities = [LearningActivity("u", "2026-01-01", "a1", "r1", "c1", True, 2, 1), LearningActivity("u", "2026-01-02", "a2", "r2", "c1", False, 0, 0), LearningActivity("u", "2026-01-02", "a3", "r3", "c2", True, 1, 1)]
        continuity = LearningContinuity()
        self.assertEqual(continuity.streak(activities), 2)
        report = continuity.weekly_report(activities, week_start="2026-01-01")
        self.assertEqual((report["attempt_records"], report["questions_attempted"], report["questions_correct"]), (2, 3, 2))

    def test_consent_quiet_hours_and_dedup(self) -> None:
        repo = CommunicationRepository.open()
        repo.set_preference(Preference("u", "telegram", True, "Asia/Kolkata", "21:00", "08:00", 1))
        quiet = repo.decide(MessageRequest("u", "telegram", "plan", "plan", "p1", "Ready", "k1"), now="2026-01-01T18:00:00+00:00")
        self.assertEqual(quiet["reason"], "quiet_hours")
        allowed = repo.decide(MessageRequest("u", "telegram", "plan", "plan", "p1", "Ready", "k2"), now="2026-01-01T10:00:00+00:00")
        duplicate = repo.decide(MessageRequest("u", "telegram", "plan", "plan", "p1", "Other", "k2"), now="2026-01-01T10:01:00+00:00")
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["decision_id"], duplicate["decision_id"])

    def test_evaluator(self) -> None:
        result = Phase9Evaluator().run()
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(len(result.checks), 11)


if __name__ == "__main__":
    unittest.main()
