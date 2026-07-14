from __future__ import annotations

import unittest

from prepdrill_content.phase10 import BillingRepository, Phase10Evaluator, Plan, ProviderEvent


class Phase10BillingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = BillingRepository.open(sandbox_secret="secret")
        self.repo.add_plan(Plan("pro", 1, 29900, 30, features=("mocks",)))

    def event(self, event_id: str, event_type: str, version: int, until: int = 2000) -> ProviderEvent:
        return ProviderEvent(event_id, "sub", "u", event_type, version, version, {"plan_id": "pro", "access_until_epoch": until})

    def test_signature_and_duplicate_handling(self) -> None:
        event = self.event("e1", "payment_completed", 1)
        signature = self.repo.sign(event, mode="sandbox")
        self.assertEqual(self.repo.ingest(event, signature=signature, mode="sandbox"), "applied")
        self.assertEqual(self.repo.ingest(event, signature=signature, mode="sandbox"), "duplicate")
        with self.assertRaises(PermissionError):
            self.repo.ingest(self.event("e2", "payment_completed", 2), signature="bad", mode="sandbox")

    def test_cancel_and_refund(self) -> None:
        for event in [self.event("e1", "payment_completed", 1), self.event("e2", "cancelled", 2)]:
            self.repo.ingest(event, signature=self.repo.sign(event, mode="sandbox"), mode="sandbox")
        self.assertEqual(self.repo.entitlement("sub", now_epoch=1500).status, "cancelled")
        refund = self.event("e3", "refunded", 3)
        self.repo.ingest(refund, signature=self.repo.sign(refund, mode="sandbox"), mode="sandbox")
        self.assertEqual(self.repo.entitlement("sub", now_epoch=1500).status, "revoked")

    def test_evaluator(self) -> None:
        result = Phase10Evaluator().run()
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(len(result.checks), 13)


if __name__ == "__main__":
    unittest.main()
