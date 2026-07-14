from __future__ import annotations

import unittest

from prepdrill_content.phase6 import AttemptEvidence, DailyPlanner, MasteryModel, MasteryState, Phase6Evaluator, PlanCandidate


class Phase6AdaptiveTests(unittest.TestCase):
    def test_mastery_direction_and_experimental_exclusion(self) -> None:
        model = MasteryModel(); start = MasteryState("c", 0.5, 1.0, 0, model.config.version)
        self.assertGreater(model.update(start, AttemptEvidence("c", True, 20_000)).score, start.score)
        self.assertLess(model.update(start, AttemptEvidence("c", False, 20_000)).score, start.score)
        self.assertEqual(model.update(start, AttemptEvidence("c", False, 20_000, experimental=True)), start)

    def test_plan_is_deterministic_and_diverse(self) -> None:
        states = {"weak": MasteryState("weak", 0.2, 0.5, 3, "v1"), "strong": MasteryState("strong", 0.9, 0.2, 5, "v1")}
        candidates = [PlanCandidate("q1", "weak", "", 0.4), PlanCandidate("q2", "weak", "", 0.4), PlanCandidate("q3", "weak", "", 0.4), PlanCandidate("q4", "strong", "", 0.7), PlanCandidate("q5", "due", "", 0.3, due=True)]
        planner = DailyPlanner(); first = planner.create(states=states, candidates=candidates, size=4, seed="s"); second = planner.create(states=states, candidates=list(reversed(candidates)), size=4, seed="s")
        self.assertEqual(first, second)
        self.assertLessEqual(sum(item.concept_id == "weak" for item in first), 2)
        self.assertTrue(all(item.rationale for item in first))

    def test_evaluator(self) -> None:
        report = Phase6Evaluator().run()
        self.assertTrue(report.passed, report.to_dict())
        self.assertGreaterEqual(len(report.checks), 13)


if __name__ == "__main__":
    unittest.main()
