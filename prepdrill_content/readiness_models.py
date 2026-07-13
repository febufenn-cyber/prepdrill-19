"""Phase 1.5 readiness contracts and SQLite schema."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

REVIEW_VERDICTS = {"pass", "needs_review", "block", "retire"}
DUPLICATE_DECISIONS = {"same_question", "distinct_questions", "retire_left", "retire_right"}
REQUIRED_REVIEW_FIELDS = {
    "revision_id", "reviewer", "verdict", "rights_ok", "answer_evidence_ok",
    "render_ok", "mapping_ok", "provenance_ok", "review_seconds",
}

READINESS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS readiness_audit_runs (
  run_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sample_target INTEGER NOT NULL,
  seed TEXT NOT NULL,
  corpus_fingerprint TEXT NOT NULL,
  population_size INTEGER NOT NULL,
  status TEXT NOT NULL,
  criteria_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS readiness_sample_items (
  run_id TEXT NOT NULL REFERENCES readiness_audit_runs(run_id),
  revision_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  unit_id TEXT NOT NULL,
  question_type TEXT NOT NULL,
  validation_tier TEXT NOT NULL,
  stratum_key TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  semantic_hash TEXT NOT NULL,
  selected_at TEXT NOT NULL,
  PRIMARY KEY(run_id, revision_id),
  UNIQUE(run_id, ordinal)
);
CREATE TABLE IF NOT EXISTS readiness_reviews (
  review_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES readiness_audit_runs(run_id),
  revision_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  verdict TEXT NOT NULL,
  rights_ok INTEGER NOT NULL,
  answer_evidence_ok INTEGER NOT NULL,
  render_ok INTEGER NOT NULL,
  mapping_ok INTEGER NOT NULL,
  provenance_ok INTEGER NOT NULL,
  review_seconds INTEGER NOT NULL,
  notes TEXT NOT NULL,
  reviewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS readiness_mapping_labels (
  label_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES readiness_audit_runs(run_id),
  revision_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS readiness_duplicate_adjudications (
  adjudication_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  decision TEXT NOT NULL,
  canonical_revision_id TEXT,
  reason TEXT NOT NULL,
  adjudicated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS readiness_gate_evaluations (
  evaluation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES readiness_audit_runs(run_id),
  corpus_fingerprint TEXT NOT NULL,
  golden_fingerprint TEXT NOT NULL,
  passed INTEGER NOT NULL,
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readiness_reviews_lookup
  ON readiness_reviews(run_id, revision_id, reviewer, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_readiness_labels_lookup
  ON readiness_mapping_labels(run_id, revision_id, reviewer, recorded_at DESC);
"""


@dataclass(frozen=True)
class GateThresholds:
    audit_target: int = 250
    golden_target: int = 100
    launch_min_published: int = 100
    mapping_min_items: int = 50
    mapping_kappa_min: float = 0.80
    dimension_pass_rate_min: float = 1.0
    max_blocking_reviews: int = 0
    max_pending_duplicates: int = 0
    required_unit_count: int = 10
    stratum_pass_rate_min: float = 1.0


@dataclass(frozen=True)
class GateFinding:
    level: str
    code: str
    message: str
    observed: Any = None
    required: Any = None


@dataclass(frozen=True)
class GateReport:
    run_id: str
    corpus_fingerprint: str
    golden_fingerprint: str
    passed: bool
    metrics: dict[str, Any]
    findings: tuple[GateFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "corpus_fingerprint": self.corpus_fingerprint,
            "golden_fingerprint": self.golden_fingerprint,
            "passed": self.passed,
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
        }
