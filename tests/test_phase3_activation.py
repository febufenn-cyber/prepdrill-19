from __future__ import annotations

import unittest

from prepdrill_content.phase3 import (
    ActivationThresholds,
    CorpusActivationRepository,
    ManifestFile,
    Phase3Evaluator,
    REQUIRED_ROLES,
    ReconciliationInput,
)


class Phase3ActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = CorpusActivationRepository.open()
        self.files = [ManifestFile(role, f"{role}.jsonl", f"checksum-{role}", 10) for role in sorted(REQUIRED_ROLES)]
        self.manifest = self.repo.register_manifest(
            delivery_name="paper1-real",
            corpus_version="v1",
            files=self.files,
            created_by="owner",
        )

    def evidence(self, **changes):
        counts = {role: 10 for role in REQUIRED_ROLES}
        payload = dict(
            declared_counts=counts,
            loaded_counts=dict(counts),
            golden_count=100,
            audit_count=250,
            phase15_gate_passed=True,
            gate_corpus_fingerprint="fp-v1",
            current_corpus_fingerprint="fp-v1",
            review_cost_measured=True,
        )
        payload.update(changes)
        return ReconciliationInput(**payload)

    def test_manifest_requires_every_role(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing manifest roles"):
            self.repo.register_manifest(
                delivery_name="bad",
                corpus_version="v1",
                files=self.files[:-1],
                created_by="owner",
            )

    def test_evaluation_fails_closed(self) -> None:
        report = self.repo.evaluate(
            self.manifest["manifest_id"],
            self.evidence(generated_items=1, orphaned_assets=1, unresolved_rights=1),
        )
        self.assertFalse(report.passed)
        self.assertIn("generated_items", report.blockers)
        self.assertIn("orphaned_assets", report.blockers)
        self.assertIn("unresolved_rights", report.blockers)

    def test_complete_current_evidence_can_be_authorized(self) -> None:
        report = self.repo.evaluate(self.manifest["manifest_id"], self.evidence())
        self.assertTrue(report.passed)
        authorization_id = self.repo.authorize(report.evaluation_id, owner="release-owner", reason="approved")
        self.assertTrue(authorization_id)
        self.assertIsNotNone(self.repo.active_authorization("fp-v1"))
        self.assertIsNone(self.repo.active_authorization("fp-v2"))

    def test_evidence_minimums_are_configurable_but_recorded(self) -> None:
        report = self.repo.evaluate(
            self.manifest["manifest_id"],
            self.evidence(golden_count=10, audit_count=20),
            ActivationThresholds(minimum_golden=10, minimum_audit=20),
        )
        self.assertTrue(report.passed)

    def test_rollback_is_compensating_not_destructive(self) -> None:
        batch = self.repo.create_migration_batch(self.manifest["manifest_id"], created_by="owner")
        self.repo.append_migration_event(batch, "loaded", {"count": 10})
        self.repo.complete_migration(batch)
        self.repo.rollback_migration(batch, actor="owner", reason="test")
        events = self.repo.connection.execute(
            "SELECT event_type FROM phase3_migration_events WHERE batch_id=? ORDER BY created_at", (batch,)
        ).fetchall()
        self.assertEqual([row[0] for row in events], ["batch_started", "loaded", "batch_completed", "rollback"])

    def test_adversarial_evaluator(self) -> None:
        report = Phase3Evaluator().run()
        self.assertTrue(report.passed, report.to_dict())
        self.assertGreaterEqual(len(report.checks), 12)


if __name__ == "__main__":
    unittest.main()
