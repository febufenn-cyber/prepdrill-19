from __future__ import annotations

import unittest

from prepdrill_content.phase12 import ContentTarget, InstituteRepository, Phase12Evaluator


class Phase12InstituteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InstituteRepository.open(min_cohort_size=2)
        self.repo.create_tenant("t", "Tenant", "owner")
        self.repo.add_member(tenant_id="t", actor_id="owner", user_id="admin", role="admin")
        self.repo.create_cohort(tenant_id="t", actor_id="admin", cohort_id="c", name="Cohort")

    def test_minimum_cohort_and_assignment_gate(self) -> None:
        self.repo.enroll(tenant_id="t", actor_id="admin", cohort_id="c", learner_id="l1")
        self.assertTrue(self.repo.aggregate_report(tenant_id="t", actor_id="admin", cohort_id="c")["suppressed"])
        with self.assertRaises(PermissionError):
            self.repo.create_assignment(tenant_id="t", actor_id="admin", cohort_id="c", target=ContentTarget("q", "published_question", False))

    def test_bulk_requires_independent_approval(self) -> None:
        operation = self.repo.propose_bulk(tenant_id="t", actor_id="admin", operation_type="archive", payload={"targets": ["a"]})
        with self.assertRaises(PermissionError):
            self.repo.approve_bulk(operation, actor_id="admin")
        self.repo.approve_bulk(operation, actor_id="owner")
        self.repo.execute_bulk(operation, actor_id="owner", current_state={"a": "active"})
        self.assertEqual(self.repo.rollback_bulk(operation, actor_id="owner"), {"a": "active"})

    def test_evaluator(self) -> None:
        result = Phase12Evaluator().run()
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(len(result.checks), 12)


if __name__ == "__main__":
    unittest.main()
