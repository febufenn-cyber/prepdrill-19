from __future__ import annotations

import unittest

from prepdrill_content.phase7 import MockExamRepository, MockQuestion, Phase7Evaluator


class Phase7MockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = MockExamRepository.open()
        self.questions = [MockQuestion("rev:1", "q:1", "A", {"question_id": "q:1", "plain_text": "Q1", "options": [{"option_id": "A"}, {"option_id": "B"}]}), MockQuestion("rev:2", "q:2", "B", {"question_id": "q:2", "plain_text": "Q2", "options": [{"option_id": "A"}, {"option_id": "B"}]})]
        self.manifest = self.repo.create_manifest(title="Mock", duration_seconds=60, questions=self.questions)

    def test_answers_hidden_until_submit(self) -> None:
        attempt = self.repo.start(manifest_id=self.manifest, learner_id="u", now="2026-01-01T00:00:00+00:00")
        self.assertNotIn("correct_option_id", attempt["questions"][0])
        self.repo.submit(attempt["attempt_id"], now="2026-01-01T00:00:20+00:00")
        self.assertIn("correct_option_id", self.repo.state(attempt["attempt_id"], include_answers=True)["questions"][0])

    def test_palette_and_scoring(self) -> None:
        attempt = self.repo.start(manifest_id=self.manifest, learner_id="u2", now="2026-01-01T00:00:00+00:00")
        saved = self.repo.save(attempt_id=attempt["attempt_id"], ordinal=0, selected_option_id="A", marked_for_review=True, idempotency_key="r", now="2026-01-01T00:00:10+00:00")
        self.assertEqual(saved["palette_state"], "answered_marked")
        result = self.repo.submit(attempt["attempt_id"], now="2026-01-01T00:00:20+00:00")
        self.assertEqual((result.score, result.correct, result.unanswered), (2, 1, 1))

    def test_evaluator(self) -> None:
        report = Phase7Evaluator().run()
        self.assertTrue(report.passed, report.to_dict())
        self.assertGreaterEqual(len(report.checks), 12)


if __name__ == "__main__":
    unittest.main()
