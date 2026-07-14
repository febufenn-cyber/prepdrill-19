from __future__ import annotations

import unittest

from prepdrill_content.phase13 import GeneratedCandidate, GeneratedContentRepository, Phase13Evaluator


class Phase13QuarantineTests(unittest.TestCase):
    def candidate(self, **changes):
        value = dict(source_revision_id="rev", concept_id="c", generation_request_id="g", prompt_version="p", model_version="m", question_text="Question", options={"A": "One", "B": "Two"}, claimed_answer_id="A", target_difficulty=.5, estimated_difficulty=.5, maximum_similarity=.4, generation_cost_micros=100)
        value.update(changes)
        return GeneratedCandidate(**value)

    def test_human_promotion_and_isolation(self) -> None:
        repo = GeneratedContentRepository.open(); candidate_id = repo.register(self.candidate())
        repo.add_solver_claim(candidate_id=candidate_id, solver_id="s1", answer_id="A", evidence="solve 1")
        repo.add_solver_claim(candidate_id=candidate_id, solver_id="s2", answer_id="A", evidence="solve 2")
        self.assertTrue(repo.evaluate(candidate_id).passed)
        self.assertFalse(repo.policy(candidate_id)["shadow_practice"])
        repo.promote(candidate_id, reviewer="expert", reason="reviewed")
        policy = repo.policy(candidate_id)
        self.assertTrue(policy["shadow_practice"])
        self.assertFalse(policy["official_archive"])
        self.assertFalse(policy["mastery_default"])

    def test_disagreement_blocks(self) -> None:
        repo = GeneratedContentRepository.open(); candidate_id = repo.register(self.candidate(generation_request_id="g2"))
        repo.add_solver_claim(candidate_id=candidate_id, solver_id="s1", answer_id="A", evidence="solve 1")
        repo.add_solver_claim(candidate_id=candidate_id, solver_id="s2", answer_id="B", evidence="solve 2")
        self.assertIn("solver_disagreement", repo.evaluate(candidate_id).blockers)

    def test_evaluator(self) -> None:
        result = Phase13Evaluator().run()
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(len(result.checks), 12)


if __name__ == "__main__":
    unittest.main()
