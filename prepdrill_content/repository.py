"""SQLite reference repository enforcing Phase 1 boundaries."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .ids import canonical_json, content_hash, exact_fingerprint, near_fingerprint, stable_id
from .models import semantic_payload, utc_now
from .validators import Finding, ValidationReport, validate_question

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS import_batches (
  import_batch_id TEXT PRIMARY KEY,
  adapter_name TEXT NOT NULL,
  adapter_version TEXT NOT NULL,
  source_document_id TEXT NOT NULL,
  source_checksum TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(adapter_name, adapter_version, source_document_id, source_checksum)
);
CREATE TABLE IF NOT EXISTS raw_records (
  raw_record_id TEXT PRIMARY KEY,
  import_batch_id TEXT NOT NULL REFERENCES import_batches(import_batch_id),
  source_locator TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  raw_checksum TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(import_batch_id, source_locator, raw_checksum)
);
CREATE TABLE IF NOT EXISTS canonical_questions (
  question_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_revisions (
  revision_id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL REFERENCES canonical_questions(question_id),
  version INTEGER NOT NULL,
  content_json TEXT NOT NULL,
  semantic_hash TEXT NOT NULL,
  exact_fingerprint TEXT NOT NULL,
  near_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  supersedes_revision_id TEXT REFERENCES question_revisions(revision_id),
  UNIQUE(question_id, version),
  UNIQUE(question_id, semantic_hash)
);
CREATE TABLE IF NOT EXISTS source_links (
  source_link_id TEXT PRIMARY KEY,
  revision_id TEXT NOT NULL REFERENCES question_revisions(revision_id),
  source_document_id TEXT NOT NULL,
  source_locator TEXT NOT NULL,
  provenance_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(revision_id, source_document_id, source_locator)
);
CREATE TABLE IF NOT EXISTS answer_claims (
  answer_claim_id TEXT PRIMARY KEY,
  revision_id TEXT NOT NULL REFERENCES question_revisions(revision_id),
  claimed_option_id TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  evidence_reference TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY,
  checksum TEXT NOT NULL,
  media_type TEXT NOT NULL,
  storage_ref TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shared_contexts (
  context_id TEXT PRIMARY KEY,
  content_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS validation_runs (
  validation_run_id TEXT PRIMARY KEY,
  revision_id TEXT NOT NULL REFERENCES question_revisions(revision_id),
  publication_mode INTEGER NOT NULL,
  passed INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS validation_findings (
  finding_id TEXT PRIMARY KEY,
  validation_run_id TEXT NOT NULL REFERENCES validation_runs(validation_run_id),
  level TEXT NOT NULL,
  code TEXT NOT NULL,
  path TEXT NOT NULL,
  message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_events (
  review_event_id TEXT PRIMARY KEY,
  revision_id TEXT NOT NULL REFERENCES question_revisions(revision_id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  reason TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS duplicate_candidates (
  candidate_id TEXT PRIMARY KEY,
  left_revision_id TEXT NOT NULL REFERENCES question_revisions(revision_id),
  right_revision_id TEXT NOT NULL REFERENCES question_revisions(revision_id),
  duplicate_type TEXT NOT NULL,
  confidence REAL NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(left_revision_id, right_revision_id, duplicate_type)
);
CREATE TABLE IF NOT EXISTS published_snapshots (
  published_question_id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL REFERENCES canonical_questions(question_id),
  revision_id TEXT NOT NULL UNIQUE REFERENCES question_revisions(revision_id),
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  published_at TEXT NOT NULL,
  retired_at TEXT
);
CREATE TABLE IF NOT EXISTS taxonomy_nodes (
  node_id TEXT PRIMARY KEY,
  parent_id TEXT REFERENCES taxonomy_nodes(node_id),
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  ontology_version TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_revisions_question ON question_revisions(question_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_revisions_exact ON question_revisions(exact_fingerprint);
CREATE INDEX IF NOT EXISTS idx_revisions_near ON question_revisions(near_fingerprint);
CREATE INDEX IF NOT EXISTS idx_public_question ON published_snapshots(question_id, retired_at);
"""


class ContentRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def open(cls, path: str | Path = ":memory:") -> "ContentRepository":
        connection = sqlite3.connect(str(path))
        repo = cls(connection)
        repo.initialise()
        return repo

    def initialise(self) -> None:
        self.connection.executescript(SCHEMA_SQL)
        self.connection.commit()

    def create_or_get_batch(self, *, adapter_name: str, adapter_version: str, source_document_id: str, source_checksum: str) -> tuple[str, bool]:
        row = self.connection.execute(
            "SELECT import_batch_id FROM import_batches WHERE adapter_name=? AND adapter_version=? AND source_document_id=? AND source_checksum=?",
            (adapter_name, adapter_version, source_document_id, source_checksum),
        ).fetchone()
        if row:
            return str(row[0]), False
        batch_id = stable_id("batch", adapter_name, adapter_version, source_document_id, source_checksum)
        self.connection.execute(
            "INSERT INTO import_batches VALUES (?, ?, ?, ?, ?, ?, ?)",
            (batch_id, adapter_name, adapter_version, source_document_id, source_checksum, "running", utc_now()),
        )
        self.connection.commit()
        return batch_id, True

    def complete_batch(self, batch_id: str) -> None:
        self.connection.execute("UPDATE import_batches SET status='completed' WHERE import_batch_id=?", (batch_id,))
        self.connection.commit()

    def store_raw(self, *, batch_id: str, source_locator: str, raw: dict[str, Any]) -> tuple[str, bool]:
        raw_json = canonical_json(raw)
        checksum = content_hash(raw)
        row = self.connection.execute(
            "SELECT raw_record_id FROM raw_records WHERE import_batch_id=? AND source_locator=? AND raw_checksum=?",
            (batch_id, source_locator, checksum),
        ).fetchone()
        if row:
            return str(row[0]), False
        raw_id = stable_id("raw", batch_id, source_locator, checksum)
        self.connection.execute(
            "INSERT INTO raw_records VALUES (?, ?, ?, ?, ?, ?)",
            (raw_id, batch_id, source_locator, raw_json, checksum, utc_now()),
        )
        self.connection.commit()
        return raw_id, True

    def upsert_revision(self, record: dict[str, Any]) -> tuple[str, int, bool]:
        question_id = str(record["question_id"])
        semantic_hash = content_hash(semantic_payload(record))
        row = self.connection.execute(
            "SELECT revision_id, version FROM question_revisions WHERE question_id=? AND semantic_hash=?",
            (question_id, semantic_hash),
        ).fetchone()
        if row:
            revision_id = str(row[0])
            self._attach_evidence(revision_id, record)
            self.connection.commit()
            return revision_id, int(row[1]), False
        previous = self.connection.execute(
            "SELECT revision_id, version FROM question_revisions WHERE question_id=? ORDER BY version DESC LIMIT 1",
            (question_id,),
        ).fetchone()
        version = int(previous[1]) + 1 if previous else 1
        previous_id = str(previous[0]) if previous else None
        revision_id = stable_id("rev", question_id, str(version), semantic_hash)
        self.connection.execute("INSERT OR IGNORE INTO canonical_questions VALUES (?, ?)", (question_id, utc_now())
        payload = dict(record)
        payload["version"] = version
        payload["revision_id"] = revision_id
        self.connection.execute(
            "INSERT INTO question_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision_id,
                question_id,
                version,
                canonical_json(payload),
                semantic_hash,
                exact_fingerprint(payload),
                near_fingerprint(payload),
                utc_now(),
                previous_id,
            ),
        )
        self._attach_evidence(revision_id, payload)
        self.connection.commit()
        return revision_id, version, True

    def _attach_evidence(self, revision_id: str, record: dict[str, Any]) -> None:
        provenance = record.get("provenance") or {}
        source_document_id = str(provenance.get("source_document_id") or "")
        source_locator = str(provenance.get("source_locator") or "")
        if source_document_id and source_locator:
            source_link_id = stable_id("src", revision_id, source_document_id, source_locator)
            self.connection.execute(
                "INSERT OR IGNORE INTO source_links VALUES (?, ?, ?, ?, ?, ?)",
                (source_link_id, revision_id, source_document_id, source_locator, canonical_json(provenance), utc_now()),
            )
        evidence_type = provenance.get("answer_evidence")
        if evidence_type:
            claim_id = stable_id("claim", revision_id, str(record.get("correct_option_id")), str(evidence_type), str(provenance.get("answer_key_reference") or ""))
            self.connection.execute(
                "INSERT OR IGNORE INTO answer_claims VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    claim_id, revision_id, str(record.get("correct_option_id")), str(evidence_type),
                    provenance.get("answer_key_reference"),
                    "accepted" if evidence_type != "unverified" else "unverified", utc_now(),
                ),
            )

    def get_revision(self, revision_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT content_json FROM question_revisions WHERE revision_id=?", (revision_id,)).fetchone()
        if not row:
            raise KeyError(revision_id)
        return json.loads(row[0])

    def latest_revision(self, question_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT content_json FROM question_revisions WHERE question_id=? ORDER BY version DESC LIMIT 1", (question_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def update_review_state(self, revision_id: str, *, actor: str, action: str, reason: str, workflow_state: str | None = None, issue_state: str | None = None, validation_tier: str | None = None, verification: dict[str, Any] | None = None) -> dict[str, Any]:
        before = self.get_revision(revision_id)
        after = dict(before)
        if workflow_state is not None:
            after["workflow_state"] = workflow_state
        if issue_state is not None:
            after["issue_state"] = issue_state
        if validation_tier is not None:
            after["validation_tier"] = validation_tier
        if verification is not None:
            merged = dict(after.get("verification") or {})
            merged.update(verification)
            after["verification"] = merged
        self.connection.execute("UPDATE question_revisions SET content_json=? WHERE revision_id=?", (canonical_json(after), revision_id))
        event_id = stable_id("review", revision_id, action, utc_now(), actor)
        self.connection.execute(
            "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, revision_id, actor, action, reason, canonical_json(before), canonical_json(after), utc_now()),
        )
        self.connection.commit()
        return after

    def register_asset(self, *, asset_id: str, checksum: str, media_type: str, storage_ref: str, status: str = "verified") -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO assets VALUES (?, ?, ?, ?, ?, ?)",
            (asset_id, checksum, media_type, storage_ref, status, utc_now()),
        )
        self.connection.commit()

    def register_context(self, *, context_id: str, content: dict[str, Any], status: str = "verified") -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO shared_contexts VALUES (?, ?, ?, ?, ?)",
            (context_id, canonical_json(content), content_hash(content), status, utc_now()),
        )
        self.connection.commit()

    def validate_revision(self, revision_id: str, *, publication: bool = False) -> ValidationReport:
        record = self.get_revision(revision_id)
        known_assets = {str(row[0]) for row in self.connection.execute("SELECT asset_id FROM assets WHERE status='verified'")}
        known_contexts = {str(row[0]) for row in self.connection.execute("SELECT context_id FROM shared_contexts WHERE status='verified'")}
        report = validate_question(record, publication=publication, known_assets=known_assets, known_contexts=known_contexts)
        run_id = stable_id("validation", revision_id, "publish" if publication else "normal", utc_now())
        self.connection.execute(
            "INSERT INTO validation_runs VALUES (?, ?, ?, ?, ?)",
            (run_id, revision_id, int(publication), int(report.ok), utc_now()),
        )
        for index, finding in enumerate(report.findings):
            finding_id = stable_id("finding", run_id, str(index), finding.code, finding.path)
            self.connection.execute(
                "INSERT INTOvalidation_findings VALUES (?, ?, ?, ?, ?, ?)",
                (finding_id, run_id, finding.level, finding.code, finding.path, finding.message),
            )
        self.connection.commit()
        return report

    def scan_duplicate_fingerprints(self) -> int:
        revisions = list(self.connection.execute(
            "SELECT revision_id, exact_fingerprint, near_fingerprint FROM question_revisions ORDER BY revision_id"
        ))
        inserted = 0
        for index, left in enumerate(revisions):
            for right in revisions[index + 1 :]:
                duplicate_type = None
                confidence = 0.0
                if left[1] == right[1]:
                    duplicate_type = "exact_content"
                    confidence = 1.0
                elif left[2] == right[2]:
                    duplicate_type = "near_token_set"
                    confidence = 0.95
                if duplicate_type:
                    candidate_id = stable_id("dup", str(left[0]), str(right[0]), duplicate_type)
                    cursor = self.connection.execute(
                        "INSERT OR IGNORE INTO duplicate_candidates VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (candidate_id, left[0], right[0], duplicate_type, confidence, "pending", utc_now()),
                    )
                    inserted += cursor.rowcount
        self.connection.commit()
        return inserted

    def publish(self, revision_id: str, *, actor: str, reason: str) -> str:
        report = self.validate_revision(revision_id, publication=True)
        if not report.ok:
            codes = ", ".join(sorted(report.codes()))
            raise ValueError(f"revision is not publishable: {codes}")
        record = self.get_revision(revision_id)
        question_id = str(record["question_id"])
        existing = self.connection.execute(
            "SELECT published_question_id FROM published_snapshots WHERE revision_id=?", (revision_id,)
        ).fetchone()
        if existing:
            return str(existing[0])
        self.connection.execute(
            "UPDATE published_snapshots SET retired_at=? WHERE question_id=? AND retired_at IS NULL",
            (utc_now(), question_id),
        )
        payload = dict(record)
        payload["workflow_state"] = "published"
        public_id = stable_id("pub", question_id, revision_id)
        self.connection.execute(
            "INSERT INTO published_snapshots VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (public_id, question_id, revision_id, canonical_json(payload), content_hash(payload), utc_now()),
        )
        event_id = stable_id("review", revision_id, "publish", utc_now(), actor)
        self.connection.execute(
            "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, revision_id, actor, "publish", reason, canonical_json(record), canonical_json(payload), utc_now()),
        )
        self.connection.commit()
        return public_id

    def unpublish(self, question_id: str, *, actor: str, reason: str) -> int:
        rows = list(self.connection.execute(
            "SELECT revision_id FROM published_snapshots WHERE question_id=? AND retired_at IS NULL", (question_id,)
        ))
        self.connection.execute(
            "UPDATE published_snapshots SET retired_at=? WHERE question_id=? AND retired_at IS NULL", (utc_now(), question_id)
        )
        for row in rows:
            event_id = stable_id("review", str(row[0]), "unpublish", utc_now(), actor)
            self.connection.execute(
                "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)",
                (event_id, row[0], actor, "unpublish", reason, utc_now()),
            )
        self.connection.commit()
        return len(rows)

    def readiness_report(self) -> dict[str, Any]:
        rows = [json.loads(row[0]) for row in self.connection.execute("SELECT content_json FROM question_revisions")]
        def count_by(field: str) -> dict[str, int]:
            result: dict[str, int] = {}
            for row in rows:
                value = str(row.get(field, "<missing>"))
                result[value] = result.get(value, 0) + 1
            return dict(sorted(result.items()))
        blockers: dict[str, int] = {}
        for row in rows:
            report = validate_question(row, publication=True)
            for finding in report.errors:
                blockers[finding.code] = blockers.get(finding.code, 0) + 1
        return {
            "total_revisions": len(rows),
            "canonical_questions": int(self.connection.execute("SELECT COUNT(*) FROM canonical_questions").fetchone()[0]),
            "published_active": int(self.connection.execute("SELECT COUNT(*) FROM published_snapshots WHERE retired_at IS NULL").fetchone()[0]),
            "by_tier": count_by("validation_tier"),
            "by_unit": count_by("unit_id"),
            "by_type": count_by("question_type"),
            "by_workflow": count_by("workflow_state"),
            "by_issue": count_by("issue_state"),
            "publication_blockers": dict(sorted(blockers.items())),
            "duplicate_candidates": int(self.connection.execute("SELECT COUNT(*) FROM duplicate_candidates").fetchone()[0]),
        }

    def load_taxonomy(self, payload: dict[str, Any]) -> int:
        version = str(payload["version"])
        count = 0
        for unit in payload.get("units", []):
            self._insert_taxonomy_node(unit["unit_id"], None, "unit", unit["label"], version)
            count += 1
            for topic in unit.get("topics", []):
                self._insert_taxonomy_node(topic["topic_id"], unit["unit_id"], "topic", topic["label"], version)
                count += 1
                for concept in topic.get("concepts", []):
                    self._insert_taxonomy_node(concept["concept_id"], topic["topic_id"], "concept", concept["label"], version)
                    count += 1
        self.connection.commit()
        return count

    def _insert_taxonomy_node(self, node_id: str, parent_id: str | None, node_type: str, label: str, version: str) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO taxonomy_nodes(node_id,parent_id,node_type,label,ontology_version,active) VALUES (?, ?, ?, ?, ?, 1)",
            (node_id, parent_id, node_type, label, version),
        )


class PublicContentRepository:
    """Read-only facade intentionally limited to immutable published snapshots."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def get(self, published_question_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT payload_json FROM published_snapshots WHERE published_question_id=? AND retired_at IS NULL",
            (published_question_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def latest_for_question(self, question_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT payload_json FROM published_snapshots WHERE question_id=? AND retired_at IS NULL ORDER BY published_at DESC LIMIT 1",
            (question_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, *, unit_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT payload_json FROM published_snapshots WHERE retired_at IS NULL ORDER BY published_at, published_question_id"
        )
        result = [json.loads(row[0]) for row in rows]
        if unit_id is not None:
            result = [item for item in result if item.get("unit_id") == unit_id]
        return result[: max(0, min(limit, 500))]

    def manifest(self) -> list[dict[str, str]]:
        return [dict(row) for row in self._connection.execute(
            "SELECT published_question_id, question_id, revision_id, payload_hash, published_at FROM published_snapshots WHERE retired_at IS NULL ORDER BY published_question_id"
        )]
