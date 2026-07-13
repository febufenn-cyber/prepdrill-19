from __future__ import annotations

import json
import unittest

from prepdrill_content.ids import canonical_json, content_hash
from prepdrill_content.runtime import Phase2Evaluator


class Phase2RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        evaluator = Phase2Evaluator()
        self.connection, self.runtime, self.records = evaluator._seed()

    def tearDown(self) -> None:
        self.connection.close()

    def authorize(self) -> None:
        self.runtime.authorize_launch("gate:evaluator", owner="tester", reason="test")

    def test_runtime_is_locked_until_named_authorization(self) -> None:
        with self.assertRaisesRegex(PermissionError, "no active launch authorization"):
            self.runtime.create_session("learner", size=1)
        authorization = self.runtime.authorize_launch("gate:evaluator", owner="tester", reason="reviewed")
        self.assertTrue(authorization.startswith("authorization:"))

    def test_session_returns_no_answer_or_explanation_before_attempt(self) -> None:
        self.authorize()
        session = self.runtime.create_session(
            "learner", size=2, seed="hide", now="2026-07-13T08:00:00+00:00"
        )
        for item in session["items"]:
            self.assertNotIn("correct_option_id", item["question"])
            self.assertNotIn("reviewed_explanation", item["question"])
            self.assertNotIn("reviewed_explanation", item["question"].get("metadata", {}))

    def test_scoring_mastery_recheck_and_explanation(self) -> None:
        self.authorize()
        session = self.runtime.create_session(
            "learner", size=2, seed="journey", now="2026-07-13T08:00:00+00:00"
        )
        first, second = session["items"]
        attempt_wrong = self.runtime.submit_attempt(
            session["session_id"], first["ordinal"], idempotency_key="a1",
            selected_option_id="B", now="2026-07-13T08:05:00+00:00",
        )
        repeated = self.runtime.submit_attempt(
            session["session_id"], first["ordinal"], idempotency_key="a1",
            selected_option_id="B", now="2026-07-13T08:05:00+00:00",
        )
        self.assertEqual(attempt_wrong["attempt_id"], repeated["attempt_id"])
        with self.assertRaisesRegex(ValueError, "already has"):
            self.runtime.submit_attempt(
                session["session_id"], first["ordinal"], idempotency_key="a1-other",
                selected_option_id="A", now="2026-07-13T08:06:00+00:00",
            )
        self.runtime.submit_attempt(
            session["session_id"], second["ordinal"], idempotency_key="a2",
            selected_option_id="A", now="2026-07-13T08:07:00+00:00",
        )
        completed = self.runtime.get_session(session["session_id"], include_answers=True)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["attempt_count"], 2)
        explanation = self.runtime.explain_attempt(attempt_wrong["attempt_id"])
        self.assertEqual(explanation["status"], "grounded")
        self.assertTrue(explanation["source_refs"])
        pending = self.connection.execute(
            "SELECT status, due_at FROM runtime_recheck_queue WHERE learner_id='learner'"
        ).fetchone()
        self.assertEqual(pending["status"], "pending")

    def test_unreviewed_explanation_fails_closed(self) -> None:
        target = self.records[0]
        public_id = target["published_question_id"]
        row = self.connection.execute(
            "SELECT payload_json FROM published_snapshots WHERE published_question_id=?", (public_id,)
        ).fetchone()
        payload = json.loads(row[0])
        payload.pop("reviewed_explanation", None)
        payload_hash = content_hash(payload)
        self.connection.execute(
            "UPDATE published_snapshots SET payload_json=?, payload_hash=? WHERE published_question_id=?",
            (canonical_json(payload), payload_hash, public_id),
        )
        self.connection.execute(
            "UPDATE question_revisions SET content_json=?, semantic_hash=? WHERE revision_id=?",
            (canonical_json(payload), payload_hash, target["revision_id"]),
        )
        self.connection.execute(
            "UPDATE published_snapshots SET retired_at='2026-07-13T00:00:00+00:00' WHERE published_question_id<>?",
            (public_id,),
        )
        self.connection.commit()
        fingerprint = self.runtime.corpus_fingerprint()
        report = {
            "run_id": "run:evaluator", "corpus_fingerprint": fingerprint,
            "golden_fingerprint": "golden:evaluator", "passed": True,
            "metrics": {"synthetic": True}, "findings": [],
        }
        self.connection.execute(
            "UPDATE readiness_gate_evaluations SET corpus_fingerprint=?, report_json=? WHERE evaluation_id='gate:evaluator'",
            (fingerprint, canonical_json(report)),
        )
        self.connection.commit()
        self.authorize()
        session = self.runtime.create_session(
            "learner", size=1, seed="explain", now="2026-07-13T08:00:00+00:00"
        )
        item = session["items"][0]
        attempt = self.runtime.submit_attempt(
            session["session_id"], item["ordinal"], idempotency_key="x",
            selected_option_id="B", now="2026-07-13T08:05:00+00:00",
        )
        explanation = self.runtime.explain_attempt(attempt["attempt_id"])
        self.assertEqual(explanation["status"], "unavailable")
        self.assertNotIn("summary", explanation)

    def test_corpus_drift_invalidates_authorization(self) -> None:
        self.authorize()
        payload = {
            "question_id": "q:drift", "unit_id": "u01", "primary_concept_id": "c",
            "question_type": "single_choice", "options": [{"option_id": "A"}],
            "correct_option_id": "A",
        }
        self.connection.execute("INSERT INTO canonical_questions VALUES ('q:drift', 'now')")
        self.connection.execute(
            "INSERT INTO question_revisions VALUES ('rev:drift', 'q:drift', 1, ?, ?, ?, ?, 'now', NULL)",
            (canonical_json(payload), content_hash(payload), content_hash(payload), content_hash(payload)),
        )
        self.connection.commit()
        with self.assertRaisesRegex(PermissionError, "corpus changed"):
            self.runtime.create_session("learner", size=1)

    def test_diagnosis_targets_lowest_mastery(self) -> None:
        self.authorize()
        session = self.runtime.create_session(
            "learner", size=12, seed="all", mode="mixed", now="2026-07-13T08:00:00+00:00"
        )
        for item in session["items"]:
            answer = "B" if item["question"]["primary_concept_id"] == "concept-weak" else "A"
            self.runtime.submit_attempt(
                session["session_id"], item["ordinal"],
                idempotency_key=f"d-{item['ordinal']}", selected_option_id=answer,
                now="2026-07-13T08:10:00+00:00",
            )
        diagnosis = self.runtime.diagnose("learner", now="2026-07-13T09:00:00+00:00")
        self.assertEqual(diagnosis["target_concepts"][0], "concept-weak")


if __name__ == "__main__":
    unittest.main()
