"""Phase 2 learner-runtime contracts and SQLite schema."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SESSION_MODES = {"adaptive", "mixed", "recheck"}
SESSION_STATUSES = {"active", "completed", "abandoned"}
ATTEMPT_OUTCOMES = {"correct", "incorrect", "skipped", "timeout"}
EXPLANATION_STATUSES = {"grounded", "unavailable"}

RUNTIME_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS runtime_launch_authorizations (
  authorization_id TEXT PRIMARY KEY,
  evaluation_id TEXT NOT NULL UNIQUE,
  corpus_fingerprint TEXT NOT NULL,
  owner TEXT NOT NULL,
  reason TEXT NOT NULL,
  active INTEGER NOT NULL,
  authorized_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS runtime_learners (
  learner_id TEXT PRIMARY KEY,
  timezone TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_sessions (
  session_id TEXT PRIMARY KEY,
  learner_id TEXT NOT NULL REFERENCES runtime_learners(learner_id),
  authorization_id TEXT NOT NULL REFERENCES runtime_launch_authorizations(authorization_id),
  mode TEXT NOT NULL,
  requested_size INTEGER NOT NULL,
  seed TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  correct_count INTEGER NOT NULL DEFAULT 0,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  item_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS runtime_session_items (
  session_id TEXT NOT NULL REFERENCES runtime_sessions(session_id),
  ordinal INTEGER NOT NULL,
  published_question_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  unit_id TEXT NOT NULL,
  concept_id TEXT NOT NULL,
  question_type TEXT NOT NULL,
  selection_reason TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  PRIMARY KEY(session_id, ordinal),
  UNIQUE(session_id, published_question_id)
);
CREATE TABLE IF NOT EXISTS runtime_attempts (
  attempt_id TEXT PRIMARY KEY,
  idempotency_key TEXT NOT NULL UNIQUE,
  session_id TEXT NOT NULL REFERENCES runtime_sessions(session_id),
  ordinal INTEGER NOT NULL,
  learner_id TEXT NOT NULL REFERENCES runtime_learners(learner_id),
  published_question_id TEXT NOT NULL,
  selected_option_id TEXT,
  correct_option_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  response_ms INTEGER NOT NULL,
  payload_hash TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  UNIQUE(session_id, ordinal)
);
CREATE TABLE IF NOT EXISTS runtime_concept_mastery (
  learner_id TEXT NOT NULL REFERENCES runtime_learners(learner_id),
  concept_id TEXT NOT NULL,
  attempts INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  incorrect INTEGER NOT NULL,
  skipped INTEGER NOT NULL,
  mastery_score REAL NOT NULL,
  uncertainty REAL NOT NULL,
  last_attempt_at TEXT NOT NULL,
  next_review_at TEXT NOT NULL,
  PRIMARY KEY(learner_id, concept_id)
);
CREATE TABLE IF NOT EXISTS runtime_recheck_queue (
  learner_id TEXT NOT NULL REFERENCES runtime_learners(learner_id),
  published_question_id TEXT NOT NULL,
  source_attempt_id TEXT NOT NULL REFERENCES runtime_attempts(attempt_id),
  due_at TEXT NOT NULL,
  priority INTEGER NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(learner_id, published_question_id)
);
CREATE TABLE IF NOT EXISTS runtime_explanations (
  explanation_id TEXT PRIMARY KEY,
  attempt_id TEXT NOT NULL UNIQUE REFERENCES runtime_attempts(attempt_id),
  status TEXT NOT NULL,
  explanation_json TEXT NOT NULL,
  grounding_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_daily_activity (
  learner_id TEXT NOT NULL REFERENCES runtime_learners(learner_id),
  activity_date TEXT NOT NULL,
  attempts INTEGER NOT NULL,
  correct INTEGER NOT NULL,
  completed_sessions INTEGER NOT NULL,
  PRIMARY KEY(learner_id, activity_date)
);
CREATE TABLE IF NOT EXISTS runtime_events (
  event_id TEXT PRIMARY KEY,
  learner_id TEXT,
  session_id TEXT,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_evaluations (
  evaluation_id TEXT PRIMARY KEY,
  evaluator_version TEXT NOT NULL,
  passed INTEGER NOT NULL,
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runtime_attempts_learner ON runtime_attempts(learner_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_runtime_mastery_weak ON runtime_concept_mastery(learner_id, mastery_score, next_review_at);
CREATE INDEX IF NOT EXISTS idx_runtime_recheck_due ON runtime_recheck_queue(learner_id, status, due_at, priority DESC);
CREATE TRIGGER IF NOT EXISTS runtime_attempts_immutable_update
BEFORE UPDATE ON runtime_attempts BEGIN SELECT RAISE(ABORT, 'runtime attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_attempts_immutable_delete
BEFORE DELETE ON runtime_attempts BEGIN SELECT RAISE(ABORT, 'runtime attempts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_session_items_immutable_update
BEFORE UPDATE ON runtime_session_items BEGIN SELECT RAISE(ABORT, 'runtime session items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_session_items_immutable_delete
BEFORE DELETE ON runtime_session_items BEGIN SELECT RAISE(ABORT, 'runtime session items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_explanations_immutable_update
BEFORE UPDATE ON runtime_explanations BEGIN SELECT RAISE(ABORT, 'runtime explanations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_explanations_immutable_delete
BEFORE DELETE ON runtime_explanations BEGIN SELECT RAISE(ABORT, 'runtime explanations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_events_immutable_update
BEFORE UPDATE ON runtime_events BEGIN SELECT RAISE(ABORT, 'runtime events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_events_immutable_delete
BEFORE DELETE ON runtime_events BEGIN SELECT RAISE(ABORT, 'runtime events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_evaluations_immutable_update
BEFORE UPDATE ON runtime_evaluations BEGIN SELECT RAISE(ABORT, 'runtime evaluations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS runtime_evaluations_immutable_delete
BEFORE DELETE ON runtime_evaluations BEGIN SELECT RAISE(ABORT, 'runtime evaluations are immutable'); END;
"""


@dataclass(frozen=True)
class EvaluationThresholds:
    min_checks: int = 10
    min_target_precision: float = 0.80
    min_grounded_explanation_rate: float = 1.0
    max_unpublished_leaks: int = 0
    max_duplicate_attempts: int = 0


@dataclass(frozen=True)
class EvaluationFinding:
    level: str
    code: str
    message: str
    observed: Any = None
    required: Any = None


@dataclass(frozen=True)
class EvaluationReport:
    evaluator_version: str
    passed: bool
    metrics: dict[str, Any]
    findings: tuple[EvaluationFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_version": self.evaluator_version,
            "passed": self.passed,
            "metrics": self.metrics,
            "findings": [asdict(item) for item in self.findings],
        }
