from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from prepdrill_content.dedup import duplicate_candidates
from prepdrill_content.importer import import_records
from prepdrill_content.normalizer import normalise_phase0_record
from prepdrill_content.repository import ContentRepository, PublicContentRepository
from prepdrill_content.validators import validate_question

FIXTURES = Path(__file__).parent / "fixtures"


def load_valid() -> dict:
    return json.loads((FIXTURES / "phase1_valid.jsonl").read_text(encoding="utf-8").strip())


class Phase1PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = ContentRepository.open(":memory:")

    def test_import_is_idempotent_and_preserves_raw(self) -> None:
        raw = load_valid()
        records = [("q1", raw)]
        first = import_records(
            self.repo,
            source_document_id="fixture-doc-001",
            source_checksum="checksum-1",
            records=records,
        )
        second = import_records(
            self.repo,
            source_document_id="fixture-doc-001",
            source_checksum="checksum-1",
            records=records,
        )
        self.assertTrue(first.batch_created)
        self.assertEqual(first.raw_created, 1)
        self.assertEqual(first.revisions_created, 1)
        self.assertFalse(second.batch_created)
        self.assertEqual(second.raw_reused, 1)
        self.assertEqual(second.revisions_reused, 1)
        self.assertEqual(self.repo.connection.execute("select count(*) from raw_records").fetchone()[0], 1)
        self.assertEqual(self.repo.connection.execute("select count(*) from question_revisions").fetchone()[0], 1)

    def test_semantic_correction_creates_new_revision(self) -> None:
        raw = load_valid()
        canonical = normalise_phase0_record(raw, source_document_id="fixture-doc-001", source_locator="q1")
        first_id, first_version, first_created = self.repo.upsert_revision(canonical)
        corrected = dict(canonical)
        corrected["plain_text"] = canonical["plain_text"] + " (corrected wording)"
        corrected["stem_blocks"] = [{"type": "paragraph", "text": corrected["plain_text"]}]
        second_id, second_version, second_created = self.repo.upsert_revision(corrected)
        self.assertTrue(first_created and second_created)
        self.assertNotEqual(first_id, second_id)
        self.assertEqual((first_version, second_version), (1, 2))
        self.assertEqual(self.repo.latest_revision(canonical["question_id"])["version"], 2)

    def test_publication_fails_closed_then_creates_immutable_snapshot(self) -> None:
        raw = load_valid()
        canonical = normalise_phase0_record(raw, source_document_id="fixture-doc-001", source_locator="q1")
        revision_id, _, _ = self.repo.upsert_revision(canonical)
        public_id = self.repo.publish(revision_id, actor="reviewer@example", reason="fixture review complete")
        public = PublicContentRepository(self.repo.connection)
        payload = public.get(public_id)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["workflow_state"], "published")
        self.assertEqual(len(public.manifest()), 1)
        self.assertEqual(self.repo.publish(revision_id, actor="reviewer@example", reason="idempotent"), public_id)

    def test_unapproved_or_unverified_content_cannot_publish(self) -> None:
        raw = load_valid()
        raw["workflow_state"] = "normalised"
        raw["provenance"]["rights_status"] = "unknown"
        raw["verification"] = {}
        canonical = normalise_phase0_record(raw, source_document_id="fixture-doc-001", source_locator="q1")
        revision_id, _, _ = self.repo.upsert_revision(canonical)
        with self.assertRaisesRegex(ValueError, "not_approved"):
            self.repo.publish(revision_id, actor="reviewer", reason="should fail")
        self.assertEqual(PublicContentRepository(self.repo.connection).list(), [])

    def test_public_facade_has_no_raw_access_method(self) -> None:
        public = PublicContentRepository(self.repo.connection)
        self.assertFalse(hasattr(public, "get_revision"))
        self.assertFalse(hasattr(public, "store_raw"))
        self.assertFalse(hasattr(public, "connection"))
        self.assertFalse(hasattr(public, "connection_table"))

    def test_missing_asset_and_context_are_blocking(self) -> None:
        raw = load_valid()
        raw["question_type"] = "asset_dependent"
        raw["asset_ids"] = ["asset:missing"]
        raw["verification"]["assets_verified_at"] = "2026-07-12T00:00:00+00:00"
        report = validate_question(raw, publication=True, known_assets=set(), known_contexts=set())
        self.assertIn("unresolved_asset", report.codes())
        self.assertFalse(report.ok)

    def test_validation_dimensions_are_separate(self) -> None:
        raw = load_valid()
        raw["issue_state"] = "disputed"
        report = validate_question(raw, publication=True)
        self.assertIn("blocking_issue", report.codes())
        self.assertNotIn("invalid_workflow_state", report.codes())

    def test_duplicate_detection_distinguishes_exact_and_near(self) -> None:
        first = load_valid()
        second = json.loads(json.dumps(first))
        second["question_id"] = "q:research-sampling-002"
        exact = duplicate_candidates([first, second])
        self.assertEqual(exact[0]["duplicate_type"], "exact_content")
        second["plain_text"] = "Which sampling method gives each population member an equal chance?"
        second["stem_blocks"] = [{"type": "paragraph", "text": second["plain_text"]}]
        candidates = duplicate_candidates([first, second], threshold=0.6)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["duplicate_type"], "near_duplicate")

    def test_readiness_report_quantifies_blockers(self) -> None:
        valid = normalise_phase0_record(load_valid(), source_document_id="fixture-doc-001", source_locator="q1")
        self.repo.upsert_revision(valid)
        invalid = dict(valid)
        invalid["question_id"] = "q:research-sampling-003"
        invalid["workflow_state"] = "review_pending"
        invalid["issue_state"] = "blocked"
        invalid["validation_tier"] = "blocked"
        invalid["provenance"] = dict(invalid["provenance"])
        invalid["provenance"]["rights_status"] = "blocked"
        self.repo.upsert_revision(invalid)
        report = self.repo.readiness_report()
        self.assertEqual(report["canonical_questions"], 2)
        self.assertEqual(report["by_tier"]["blocked"], 1)
        self.assertGreater(report["publication_blockers"].get("blocking_issue", 0), 0)

    def test_taxonomy_loads_all_ten_units(self) -> None:
        taxonomy = json.loads((Path(__file__).parents[1] / "taxonomy" / "paper1.v1.json").read_text(encoding="utf-8"))
        loaded = self.repo.load_taxonomy(taxonomy)
        units = self.repo.connection.execute("select count(*) from taxonomy_nodes where node_type='unit'").fetchone()[0]
        self.assertGreater(loaded, 10)
        self.assertEqual(units, 10)

    def test_reused_revision_attaches_additional_source_evidence(self) -> None:
        first = load_valid()
        canonical = normalise_phase0_record(first, source_document_id="fixture-doc-001", source_locator="q1")
        revision_id, _, _ = self.repo.upsert_revision(canonical)
        second = normalise_phase0_record(first, source_document_id="fixture-doc-002", source_locator="q9")
        reused_id, _, created = self.repo.upsert_revision(second)
        self.assertFalse(created)
        self.assertEqual(reused_id, revision_id)
        links = self.repo.connection.execute("select count(*) from source_links where revision_id=?", (revision_id,)).fetchone()[0]
        self.assertEqual(links, 2)

    def test_import_persists_validation_findings(self) -> None:
        invalid = load_valid()
        invalid["correct_option_id"] = "Z"
        result = import_records(
            self.repo, source_document_id="fixture-doc-invalid", source_checksum="checksum-invalid", records=[("q1", invalid)]
        )
        self.assertGreater(result.validation_errors, 0)
        findings = self.repo.connection.execute("select count(*) from validation_findings").fetchone()[0]
        self.assertGreater(findings, 0)


if __name__ == "__main__":
    unittest.main()
