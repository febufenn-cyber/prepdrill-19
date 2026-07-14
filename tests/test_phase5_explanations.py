from __future__ import annotations

import unittest

from prepdrill_content.phase5 import ExplanationRepository, GenerationPolicy, GroundingBundle, Phase5Evaluator


class Phase5ExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = ExplanationRepository.open()
        self.bundle = GroundingBundle("rev:1", "A", "concept:1", {"key": "A", "note": "Evidence"}, "Question?", {"A": "Right", "B": "Wrong"})

    def good(self, prompt, model):
        return {"claimed_correct_option_id": "A", "evidence_refs": ["key"], "correction": "A", "why_selected_wrong": "B conflicts with evidence", "concept_refresher": "Concept", "shortcut": "Shortcut", "related_practice": "Practice"}

    def test_clean_output_requires_human_approval(self) -> None:
        result = self.repo.generate(self.bundle, selected_option_id="B", provider=self.good)
        self.assertEqual(result.status, "pending_approval")
        self.assertEqual(self.repo.visible(result.explanation_id)["status"], "unavailable")
        approved = self.repo.approve(result.explanation_id, reviewer="expert")
        self.assertEqual(approved.status, "approved")

    def test_answer_contradiction_is_queued(self) -> None:
        result = self.repo.generate(self.bundle, selected_option_id="B", provider=lambda p, m: {**self.good(p, m), "claimed_correct_option_id": "B"})
        self.assertIn("answer_contradiction", result.blockers)
        self.assertEqual(result.status, "review")

    def test_provider_outage_is_non_blocking(self) -> None:
        result = self.repo.generate(self.bundle, selected_option_id="B", provider=lambda p, m: (_ for _ in ()).throw(RuntimeError()), policy=GenerationPolicy(prompt_version="outage"))
        self.assertEqual(result.status, "unavailable")

    def test_evaluator(self) -> None:
        report = Phase5Evaluator().run()
        self.assertTrue(report.passed, report.to_dict())
        self.assertGreaterEqual(len(report.checks), 12)


if __name__ == "__main__":
    unittest.main()
