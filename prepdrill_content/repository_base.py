"""Database initialization shared by internal repository mixins."""
from __future__ import annotations

import sqlite3
from pathlib import Path

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

class RepositoryBase:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def open(cls, path: str | Path = ":memory:") -> "RepositoryBase":
        connection = sqlite3.connect(str(path))
        repo = cls(connection)
        repo.initialise()
        return repo

    def initialise(self) -> None:
        self.connection.executescript(SCHEMA_SQL)
        self.connection.commit()
