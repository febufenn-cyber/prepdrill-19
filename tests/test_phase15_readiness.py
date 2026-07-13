from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prepdrill_content.ids import canonical_json, content_hash, stable_id
from prepdrill_content.readiness import ReadinessRepository

CORE_SQL = """
CREATE TABLE question_revisions (
  revision_id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  content_json TEXT NOT NULL,
  semantic_hash TEXT NOT NULL
);
CREATE TABLE duplicate_candidates (
  candidate_id TEXT PRIMARY KEY,
  left_revision_id TEXT NOT NULL,
  right_revision_id TEXT NOT NULL,
  duplicate_type TEXT NOT NULL,
  confidence REAL NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE published_snapshots (
  published_question_id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  published_at TEXT NOT NULL,
  retired_at TEXT
);
CREATE TABLE import_batches (
  import_batch_id TEXT PRIMARY KEY, adapter_name TEXT, adapter_version TEXT,
  source_document_id TEXT, source_checksum TEXT, status TEXT, created_at TEXT
);
CREATE TABLE source_links (
  source_link_id TEXT PRIMARY KEY, revision_id TEXT, source_document_id TEXT,
  source_locator TEXT, provenance_json TEXT, created_at TEXT
);
CREATE TABLE validation_runs (
  validation_run_id TEXT PRIMARY KEY, revision_id TEXT, publication_mode INTEGER,
  passed INTEGER, created_at TEXT
);
CREATE TABLE validation_findings (
  finding_id TEXT PRIMARY KEY, validation_run_id TEXT, level TEXT, code TEXT, path TEXT, message TEXT
);
CREATE TABLE taxonomy_nodes (
  node_id TEXT PRIMARY KEY,
  parent_id TEXT,
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  ontology_version TEXT NOT NULL,
  active INTEGER NOT NULL
);
"""


class ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(CORE_SQL)
        for unit in range(1, 11):
            self.connection.execute(
                "INSERT INTO taxonomy_nodes VALUES (?, NULL, 'unit', ?, 'v1', 1)",
                (f"u{unit:02d}", f"Unit {unit}"),
            )
        self.repo = ReadinessRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def add_population(self, count: int = 250) -> list[dict]:
        records = []
        question_types = ["single_choice", "assertion_reason", "match_following", "passage_linked", "table_based", "calculation", "multi_statement", "asset_dependent"]
        tiers = ["gold", "silver", "review", "blocked", "retired"]
        for index in range(count):
            question_id = f"q:{index:04d}"
            revision_id = f"rev:{index:04d}"
            payload = {
                "question_id": question_id,
                "unit_id": f"u{(index % 10) + 1:02d}",
                "question_type": question_types[index % len(question_types)],
                "validation_tier": tiers[index % len(tiers)],
                "primary_concept_id": f"concept-{index % 7}",
            }
            semantic_hash = content_hash(payload)
            self.connection.execute(
                "INSERT INTO question_revisions VALUES (?, ?, 1, ?, ?)",
                (revision_id, question_id, canonical_json(payload), semantic_hash),
            )
            source_document_id = f"source-doc-{index:04d}"
            source_checksum = f"source-{revision_id}"
            self.connection.execute(
                "INSERT INTO import_batches VALUES (?, 'fixture', '1', ?, ?, 'completed', '2026-01-01')",
                (f"batch-{index:04d}", source_document_id, source_checksum),
            )
            self.connection.execute(
                "INSERT INTO source_links VALUES (?, ?, ?, 'q1', '{}', '2026-01-01')",
                (f"link-{index:04d}", revision_id, source_document_id),
            )
            self.connection.execute(
                "INSERT INTO validation_runs VALUES (?, ?, 0, 1, '2026-01-01')",
                (f"validation-{index:04d}", revision_id),
            )
            records.append({"revision_id": revision_id, "question_id": question_id, "payload": payload, "semantic_hash": semantic_hash})
        self.connection.commit()
        return records

    def golden_manifest(self, records: list[dict], count: int = 100) -> dict:
        entries = []
        for record in records[:count]:
            payload = record["payload"]
            entries.append({
                "revision_id": record["revision_id"],
                "question_id": record["question_id"],
                "unit_id": payload["unit_id"],
                "question_type": payload["question_type"],
                "source_checksum": f"source-{record['revision_id']}",
                "expected_canonical_hash": record["semantic_hash"],
                "expected_validator_codes": [],
            })
        return {"version": "golden-set.v1", "target_size": count, "current_size": count, "entries": entries}

    def add_review_evidence(self, run_id: str, sample_count: int = 250) -> None:
        sample = list(self.connection.execute(
            "SELECT revision_id, ordinal FROM readiness_sample_items WHERE run_id=? ORDER BY ordinal", (run_id,)
        ))
        for row in sample[:sample_count]:
            self.repo.record_review(run_id, {
                "revision_id": row["revision_id"],
                "reviewer": "reviewer-a",
                "verdict": "pass",
                "rights_ok": True,
                "answer_evidence_ok": True,
                "render_ok": True,
                "mapping_ok": True,
                "provenance_ok": True,
                "review_seconds": 90,
            })
        for row in sample[:50]:
            item = self.connection.execute(
                "SELECT content_json FROM question_revisions WHERE revision_id=?", (row["revision_id"],)
            ).fetchone()
            concept = json.loads(item[0])["primary_concept_id"]
            for reviewer in ("mapper-a", "mapper-b"):
                self.repo.record_mapping_label(run_id, {
                    "revision_id": row["revision_id"], "reviewer": reviewer, "concept_id": concept,
                })

    def publish(self, records: list[dict], count: int = 100) -> None:
        for record in records[:count]:
            self.connection.execute(
                "INSERT INTO published_snapshots VALUES (?, ?, ?, ?, ?, '2026-01-01', NULL)",
                (
                    stable_id("pub", record["question_id"]), record["question_id"], record["revision_id"],
                    canonical_json(record["payload"]), record["semantic_hash"],
                ),
            )
        self.connection.commit()

    def test_stratified_sampling_is_deterministic_and_idempotent(self) -> None:
        self.add_population(80)
        first = self.repo.create_audit_run(name="audit", sample_target=40, seed="fixed")
        selected_first = [row[0] for row in self.connection.execute(
            "SELECT revision_id FROM readiness_sample_items WHERE run_id=? ORDER BY ordinal", (first["run_id"],)
        )]
        second = self.repo.create_audit_run(name="audit", sample_target=40, seed="fixed")
        selected_second = [row[0] for row in self.connection.execute(
            "SELECT revision_id FROM readiness_sample_items WHERE run_id=? ORDER BY ordinal", (second["run_id"],)
        )]
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(selected_first, selected_second)
        self.assertEqual(len(selected_first), 40)
        breakdown = self.repo.audit_report(first["run_id"])["sample_breakdown"]
        self.assertEqual(len(breakdown["unit_id"]), 10)
        self.assertEqual(len(breakdown["question_type"]), 8)

    def test_launch_gate_fails_closed_without_evidence(self) -> None:
        records = self.add_population(250)
        run = self.repo.create_audit_run(name="audit", sample_target=250)
        report = self.repo.evaluate_launch_gate(run["run_id"], self.golden_manifest(records, 100))
        self.assertFalse(report.passed)
        codes = {finding.code for finding in report.findings}
        self.assertIn("audit_incomplete", codes)
        self.assertIn("launch_subset_small", codes)
        self.assertIn("mapping_kappa_low", codes)
        self.assertIn("review_time_missing", codes)

    def test_complete_evidence_can_pass_gate(self) -> None:
        records = self.add_population(250)
        run = self.repo.create_audit_run(name="audit", sample_target=250)
        self.add_review_evidence(run["run_id"])
        self.publish(records, 100)
        report = self.repo.evaluate_launch_gate(run["run_id"], self.golden_manifest(records, 100))
        self.assertTrue(report.passed, [finding.code for finding in report.findings])
        self.assertEqual(report.metrics["audit"]["review_coverage"], 1.0)
        self.assertEqual(report.metrics["audit"]["mapping_agreement"]["minimum_pair_kappa"], 1.0)
        stored = self.connection.execute("SELECT passed FROM readiness_gate_evaluations").fetchone()
        self.assertEqual(stored[0], 1)

    def test_gate_detects_corpus_drift(self) -> None:
        records = self.add_population(250)
        run = self.repo.create_audit_run(name="audit", sample_target=250)
        self.add_review_evidence(run["run_id"])
        self.publish(records, 100)
        payload = {"question_id": "q:new", "unit_id": "u01", "question_type": "single_choice", "validation_tier": "gold", "primary_concept_id": "c"}
        self.connection.execute(
            "INSERT INTO question_revisions VALUES ('rev:new', 'q:new', 1, ?, ?)",
            (canonical_json(payload), content_hash(payload)),
        )
        self.connection.commit()
        report = self.repo.evaluate_launch_gate(run["run_id"], self.golden_manifest(records, 100))
        self.assertFalse(report.passed)
        self.assertIn("audit_stale", {finding.code for finding in report.findings})

    def test_golden_manifest_detects_hash_and_coverage_failures(self) -> None:
        records = self.add_population(100)
        manifest = self.golden_manifest(records, 100)
        manifest["entries"][0]["expected_canonical_hash"] = "wrong"
        manifest["entries"] = [entry for entry in manifest["entries"] if entry["unit_id"] != "u10"]
        manifest["current_size"] = len(manifest["entries"])
        result = self.repo.validate_golden_manifest(
            manifest,
            required_units={f"u{unit:02d}" for unit in range(1, 11)},
            required_types={"single_choice", "assertion_reason", "match_following", "passage_linked", "table_based", "calculation", "multi_statement", "asset_dependent"},
        )
        self.assertFalse(result["ok"])
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("expected_canonical_hash_mismatch", codes)
        self.assertIn("missing_units", codes)
        self.assertIn("golden_set_incomplete", codes)

    def test_ingest_reviews_is_resumable(self) -> None:
        self.add_population(2)
        run = self.repo.create_audit_run(name="small", sample_target=2)
        sample_id = self.connection.execute(
            "SELECT revision_id FROM readiness_sample_items WHERE run_id=? LIMIT 1", (run["run_id"],)
        ).fetchone()[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.jsonl"
            valid = {
                "revision_id": sample_id, "reviewer": "a", "verdict": "pass",
                "rights_ok": True, "answer_evidence_ok": True, "render_ok": True,
                "mapping_ok": True, "provenance_ok": True, "review_seconds": 30,
            }
            invalid = dict(valid)
            invalid["revision_id"] = "rev:not-sampled"
            path.write_text(json.dumps(valid) + "\n" + json.dumps(invalid) + "\n", encoding="utf-8")
            result = self.repo.ingest_reviews(run["run_id"], path)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(len(result["errors"]), 1)

    def test_duplicate_adjudication_is_audited_and_clears_pending_gate(self) -> None:
        self.add_population(2)
        run = self.repo.create_audit_run(name="dups", sample_target=2)
        revisions = [row[0] for row in self.connection.execute(
            "SELECT revision_id FROM readiness_sample_items WHERE run_id=? ORDER BY ordinal", (run["run_id"],)
        )]
        self.connection.execute(
            "INSERT INTO duplicate_candidates VALUES ('dup:1', ?, ?, 'near_token_set', 0.95, 'pending', '2026-01-01')",
            (revisions[0], revisions[1]),
        )
        self.connection.commit()
        self.assertEqual(self.repo.audit_report(run["run_id"])["pending_duplicate_candidates"], 1)
        adjudication_id = self.repo.adjudicate_duplicate(
            "dup:1", reviewer="reviewer-a", decision="distinct_questions", reason="Different learning objective"
        )
        self.assertTrue(adjudication_id.startswith("adjudication:"))
        self.assertEqual(self.repo.audit_report(run["run_id"])["pending_duplicate_candidates"], 0)
        row = self.connection.execute(
            "SELECT decision FROM readiness_duplicate_adjudications WHERE candidate_id='dup:1'"
        ).fetchone()
        self.assertEqual(row[0], "distinct_questions")

    def test_review_boolean_fields_must_be_real_booleans(self) -> None:
        self.add_population(1)
        run = self.repo.create_audit_run(name="boolean", sample_target=1)
        revision_id = self.connection.execute(
            "SELECT revision_id FROM readiness_sample_items WHERE run_id=?", (run["run_id"],)
        ).fetchone()[0]
        with self.assertRaisesRegex(ValueError, "rights_ok must be a JSON boolean"):
            self.repo.record_review(run["run_id"], {
                "revision_id": revision_id, "reviewer": "a", "verdict": "pass",
                "rights_ok": "false", "answer_evidence_ok": True, "render_ok": True,
                "mapping_ok": True, "provenance_ok": True, "review_seconds": 30,
            })


if __name__ == "__main__":
    unittest.main()
