"""Adversarial evaluator for the Phase 2 learner runtime."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Any

from .ids import canonical_json, content_hash, stable_id
from .models import utc_now
from .runtime_attempts import RuntimeAttemptsMixin
from .runtime_base import RuntimeBase
from .runtime_insights import RuntimeInsightsMixin
from .runtime_selection import RuntimeSelectionMixin
from .runtime_models import EvaluationFinding, EvaluationReport, EvaluationThresholds


class _EvaluatorRuntime(RuntimeSelectionMixin, RuntimeAttemptsMixin, RuntimeInsightsMixin, RuntimeBase):
    pass

EVALUATOR_VERSION = "phase2-evaluator.v1"

EVALUATOR_CORE_SQL = """
CREATE TABLE canonical_questions (
  question_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);
CREATE TABLE question_revisions (
  revision_id TEXT PRIMARY KEY,
  question_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  content_json TEXT NOT NULL,
  semantic_hash TEXT NOT NULL,
  exact_fingerprint TEXT NOT NULL,
  near_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  supersedes_revision_id TEXT
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
CREATE TABLE readiness_audit_runs (
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
CREATE TABLE readiness_gate_evaluations (
  evaluation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  corpus_fingerprint TEXT NOT NULL,
  golden_fingerprint TEXT NOT NULL,
  passed INTEGER NOT NULL,
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class Phase2Evaluator:
    """Runs a deterministic synthetic learner journey against the actual runtime code."""

    def __init__(self, thresholds: EvaluationThresholds | None = None):
        self.thresholds = thresholds or EvaluationThresholds()

    @staticmethod
    def _question(index: int, *, published: bool = True) -> dict[str, Any]:
        concept = "concept-weak" if index < 6 else "concept-strong"
        question_id = f"q:evaluator-{index:02d}"
        revision_id = f"rev:evaluator-{index:02d}"
        payload = {
            "question_id": question_id,
            "revision_id": revision_id,
            "version": 1,
            "exam": "ugc_net",
            "paper": "paper_1",
            "unit_id": f"u{(index % 10) + 1:02d}",
            "primary_concept_id": concept,
            "secondary_concept_ids": [],
            "question_type": "single_choice",
            "plain_text": f"Evaluator question {index}?",
            "options": [
                {"option_id": "A", "plain_text": "Correct"},
                {"option_id": "B", "plain_text": "Incorrect"},
            ],
            "correct_option_id": "A",
            "workflow_state": "published" if published else "approved",
            "issue_state": "clear",
            "validation_tier": "gold",
            "reviewed_explanation": {
                "summary": f"Reviewed explanation for question {index}.",
                "why_correct": "Option A matches the reviewed source evidence.",
                "why_others_wrong": {"B": "Option B conflicts with the reviewed evidence."},
                "source_refs": [f"source:evaluator:{index}"],
                "reviewed_at": "2026-07-13T00:00:00+00:00",
            },
            "metadata": {},
        }
        return {
            "question_id": question_id,
            "revision_id": revision_id,
            "payload": payload,
            "published": published,
        }

    def _seed(self) -> tuple[sqlite3.Connection, _EvaluatorRuntime, list[dict[str, Any]]]:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(EVALUATOR_CORE_SQL)
        runtime = _EvaluatorRuntime(connection)
        records = [self._question(index, published=index < 12) for index in range(13)]
        for record in records:
            semantic_hash = content_hash({
                key: record["payload"].get(key)
                for key in (
                    "exam", "paper", "unit_id", "primary_concept_id", "question_type",
                    "plain_text", "options", "correct_option_id",
                )
            })
            connection.execute(
                "INSERT INTO canonical_questions VALUES (?, ?)",
                (record["question_id"], "2026-07-13T00:00:00+00:00"),
            )
            connection.execute(
                "INSERT INTO question_revisions VALUES (?, ?, 1, ?, ?, ?, ?, ?, NULL)",
                (
                    record["revision_id"], record["question_id"], canonical_json(record["payload"]),
                    semantic_hash, content_hash(record["payload"]), content_hash(sorted(record["payload"]["plain_text"].split())),
                    "2026-07-13T00:00:00+00:00",
                ),
            )
            if record["published"]:
                public_id = stable_id("pub", record["question_id"], record["revision_id"])
                connection.execute(
                    "INSERT INTO published_snapshots VALUES (?, ?, ?, ?, ?, ?, NULL)",
                    (
                        public_id, record["question_id"], record["revision_id"],
                        canonical_json(record["payload"]), content_hash(record["payload"]),
                        "2026-07-13T00:00:00+00:00",
                    ),
                )
                record["published_question_id"] = public_id
        connection.commit()
        fingerprint = runtime.corpus_fingerprint()
        run_id = "run:evaluator"
        gate_id = "gate:evaluator"
        connection.execute(
            "INSERT INTO readiness_audit_runs VALUES (?, ?, 250, 'evaluator', ?, ?, 'completed', '{}', ?, ?)",
            (run_id, "Phase 2 evaluator gate", fingerprint, len(records), utc_now(), utc_now()),
        )
        gate_report = {
            "run_id": run_id,
            "corpus_fingerprint": fingerprint,
            "golden_fingerprint": "golden:evaluator",
            "passed": True,
            "metrics": {"synthetic": True},
            "findings": [],
        }
        connection.execute(
            "INSERT INTO readiness_gate_evaluations VALUES (?, ?, ?, ?, 1, ?, ?)",
            (gate_id, run_id, fingerprint, "golden:evaluator", canonical_json(gate_report), utc_now()),
        )
        connection.commit()
        return connection, runtime, records

    def run(self) -> EvaluationReport:
        connection, runtime, records = self._seed()
        findings: list[EvaluationFinding] = []
        metrics: dict[str, Any] = {}
        checks = 0

        def check(code: str, ok: bool, message: str, observed: Any = None, required: Any = True) -> None:
            nonlocal checks
            checks += 1
            if not ok:
                findings.append(EvaluationFinding("error", code, message, observed, required))

        try:
            try:
                runtime.create_session("learner-locked", size=2, seed="locked", now="2026-07-13T08:00:00+00:00")
                locked = False
            except PermissionError:
                locked = True
            check("gate_not_enforced", locked, "runtime must reject sessions before named launch authorization")

            authorization_id = runtime.authorize_launch(
                "gate:evaluator", owner="phase2-evaluator", reason="synthetic invariant evaluation"
            )
            metrics["authorization_id"] = authorization_id

            first = runtime.create_session(
                "learner-a", size=12, seed="deterministic", mode="mixed",
                now="2026-07-13T09:00:00+00:00",
            )
            second = runtime.create_session(
                "learner-b", size=12, seed="deterministic", mode="mixed",
                now="2026-07-13T09:00:00+00:00",
            )
            first_ids = [item["published_question_id"] for item in first["items"]]
            second_ids = [item["published_question_id"] for item in second["items"]]
            determinism = float(first_ids == second_ids)
            metrics["selection_determinism"] = determinism
            check("selection_nondeterministic", first_ids == second_ids, "identical learner state and seed must select identical snapshots", first_ids, second_ids)

            unpublished_revision = records[-1]["revision_id"]
            selected_revisions = {item["revision_id"] for item in first["items"] + second["items"]}
            unpublished_leaks = int(unpublished_revision in selected_revisions)
            metrics["unpublished_leaks"] = unpublished_leaks
            check(
                "unpublished_content_leak", unpublished_leaks <= self.thresholds.max_unpublished_leaks,
                "session selection must use active published snapshots only", unpublished_leaks,
                self.thresholds.max_unpublished_leaks,
            )

            duplicate_attempts = 0
            attempts: list[dict[str, Any]] = []
            for item in first["items"]:
                concept = item["question"]["primary_concept_id"]
                selected = "B" if concept == "concept-weak" else "A"
                attempt = runtime.submit_attempt(
                    first["session_id"], item["ordinal"],
                    idempotency_key=f"eval-attempt-{item['ordinal']}",
                    selected_option_id=selected,
                    response_ms=1200,
                    now="2026-07-13T09:10:00+00:00",
                )
                attempts.append(attempt)
                if item["ordinal"] == 0:
                    repeated = runtime.submit_attempt(
                        first["session_id"], item["ordinal"],
                        idempotency_key=f"eval-attempt-{item['ordinal']}",
                        selected_option_id=selected,
                        response_ms=1200,
                        now="2026-07-13T09:10:00+00:00",
                    )
                    duplicate_attempts += int(repeated["attempt_id"] != attempt["attempt_id"])
            metrics["duplicate_attempts"] = duplicate_attempts
            check(
                "idempotency_broken", duplicate_attempts <= self.thresholds.max_duplicate_attempts,
                "replayed idempotency keys must not create new attempts", duplicate_attempts,
                self.thresholds.max_duplicate_attempts,
            )

            completed = runtime.get_session(first["session_id"], include_answers=True)
            expected_correct = sum(1 for item in first["items"] if item["question"]["primary_concept_id"] == "concept-strong")
            metrics["score"] = {"correct": completed["correct_count"], "attempts": completed["attempt_count"], "items": completed["item_count"]}
            check("score_incorrect", int(completed["correct_count"]) == expected_correct, "session score must equal immutable attempt outcomes", completed["correct_count"], expected_correct)
            check("session_not_completed", completed["status"] == "completed", "session must complete after every item has one attempt", completed["status"], "completed")

            mastery = {
                row["concept_id"]: float(row["mastery_score"])
                for row in connection.execute("SELECT concept_id, mastery_score FROM runtime_concept_mastery WHERE learner_id='learner-a'")
            }
            metrics["mastery"] = mastery
            check("wrong_mastery_direction", mastery.get("concept-weak", 0.5) < 0.5, "incorrect answers must lower posterior mastery", mastery.get("concept-weak"), "< 0.5")
            check("correct_mastery_direction", mastery.get("concept-strong", 0.5) > 0.5, "correct answers must raise posterior mastery", mastery.get("concept-strong"), "> 0.5")

            targeted = runtime.create_session(
                "learner-a", size=5, seed="targeted", mode="adaptive",
                now="2026-07-13T10:00:00+00:00",
            )
            weak_count = sum(1 for item in targeted["items"] if item["question"]["primary_concept_id"] == "concept-weak")
            target_precision = weak_count / len(targeted["items"])
            metrics["target_precision"] = target_precision
            check(
                "weakness_targeting_low", target_precision >= self.thresholds.min_target_precision,
                "adaptive selection must concentrate on the weakest concept", target_precision,
                self.thresholds.min_target_precision,
            )

            connection.execute(
                "UPDATE runtime_recheck_queue SET due_at='2026-07-13T10:30:00+00:00' WHERE learner_id='learner-a' AND status='pending'"
            )
            connection.commit()
            recheck = runtime.create_session(
                "learner-a", size=3, seed="recheck", mode="recheck",
                now="2026-07-13T11:00:00+00:00",
            )
            recheck_reasons = {item["selection_reason"] for item in recheck["items"]}
            metrics["recheck_reasons"] = sorted(recheck_reasons)
            check("recheck_priority_broken", recheck_reasons == {"due_recheck"}, "recheck mode must contain due rechecks only", sorted(recheck_reasons), ["due_recheck"])

            grounded = 0
            for attempt in attempts:
                explanation = runtime.explain_attempt(attempt["attempt_id"])
                grounded += int(explanation["status"] == "grounded")
            grounded_rate = grounded / len(attempts)
            metrics["grounded_explanation_rate"] = grounded_rate
            check(
                "explanation_grounding_low", grounded_rate >= self.thresholds.min_grounded_explanation_rate,
                "reviewed explanations must remain source-grounded", grounded_rate,
                self.thresholds.min_grounded_explanation_rate,
            )

            diagnosis = runtime.diagnose("learner-a", now="2026-07-13T11:00:00+00:00")
            metrics["diagnosis_targets"] = diagnosis["target_concepts"]
            check("diagnosis_missed_weakness", diagnosis["target_concepts"][0] == "concept-weak", "diagnosis must rank the weakest concept first", diagnosis["target_concepts"], ["concept-weak"])

            new_question = self._question(99, published=False)
            semantic_hash = content_hash(new_question["payload"])
            connection.execute("INSERT INTO canonical_questions VALUES (?, ?)", (new_question["question_id"], utc_now()))
            connection.execute(
                "INSERT INTO question_revisions VALUES (?, ?, 1, ?, ?, ?, ?, ?, NULL)",
                (
                    new_question["revision_id"], new_question["question_id"], canonical_json(new_question["payload"]),
                    semantic_hash, semantic_hash, semantic_hash, utc_now(),
                ),
            )
            connection.commit()
            try:
                runtime.create_session("learner-stale", size=1, seed="stale", now="2026-07-13T12:00:00+00:00")
                stale_locked = False
            except PermissionError:
                stale_locked = True
            metrics["stale_authorization_locked"] = stale_locked
            check("stale_gate_accepted", stale_locked, "any corpus drift must invalidate the launch authorization")

            metrics["checks_run"] = checks
            check("too_few_checks", checks >= self.thresholds.min_checks, "evaluator must execute the minimum invariant set", checks, self.thresholds.min_checks)
            report = EvaluationReport(EVALUATOR_VERSION, not findings, metrics, tuple(findings))
            evaluation_id = stable_id("runtime-eval", EVALUATOR_VERSION, content_hash(report.to_dict()))
            connection.execute(
                "INSERT INTO runtime_evaluations VALUES (?, ?, ?, ?, ?)",
                (evaluation_id, EVALUATOR_VERSION, int(report.passed), canonical_json(report.to_dict()), utc_now()),
            )
            connection.commit()
            return report
        finally:
            connection.close()
