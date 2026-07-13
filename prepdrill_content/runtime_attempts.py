"""Immutable attempt submission, scoring, mastery, activity, and re-checks."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .ids import stable_id
from .models import utc_now


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class RuntimeAttemptsMixin:
    def submit_attempt(self, session_id: str, ordinal: int, *, idempotency_key: str, selected_option_id: str | None, response_ms: int=0, timed_out: bool=False, now: str | None=None) -> dict[str, Any]:
        existing = self.connection.execute('SELECT * FROM runtime_attempts WHERE idempotency_key=?', (idempotency_key,)).fetchone()
        if existing:
            return dict(existing)
        session = self.connection.execute('SELECT * FROM runtime_sessions WHERE session_id=?', (session_id,)).fetchone()
        if not session:
            raise KeyError(session_id)
        if session['status'] != 'active':
            raise ValueError('session is not active')
        item = self.connection.execute('\n                    SELECT rsi.*, ps.payload_json, ps.payload_hash AS current_payload_hash\n                    FROM runtime_session_items rsi\n                    JOIN published_snapshots ps ON ps.published_question_id=rsi.published_question_id\n                    WHERE rsi.session_id=? AND rsi.ordinal=?\n                    ', (session_id, ordinal)).fetchone()
        if not item:
            raise ValueError('session item does not exist')
        if str(item['payload_hash']) != str(item['current_payload_hash']):
            raise ValueError('published snapshot changed after session creation')
        payload = json.loads(item['payload_json'])
        correct_option_id = str(payload.get('correct_option_id') or '')
        if not correct_option_id:
            raise ValueError('published question has no correct option')
        option_ids = {str(option.get('option_id')) for option in payload.get('options', [])}
        if selected_option_id is not None and selected_option_id not in option_ids:
            raise ValueError('selected option is not part of the question')
        if timed_out:
            outcome = 'timeout'
        elif selected_option_id is None:
            outcome = 'skipped'
        elif selected_option_id == correct_option_id:
            outcome = 'correct'
        else:
            outcome = 'incorrect'
        submitted_at = now or utc_now()
        attempt_id = stable_id('attempt', session_id, str(ordinal), idempotency_key)
        try:
            self.connection.execute('INSERT INTO runtime_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (attempt_id, idempotency_key, session_id, ordinal, session['learner_id'], item['published_question_id'], selected_option_id, correct_option_id, outcome, max(0, int(response_ms)), item['payload_hash'], submitted_at))
        except Exception:
            same_item = self.connection.execute('SELECT * FROM runtime_attempts WHERE session_id=? AND ordinal=?', (session_id, ordinal)).fetchone()
            if same_item:
                raise ValueError('session item already has a submitted attempt')
            raise
        self._update_mastery(learner_id=str(session['learner_id']), concept_id=str(item['concept_id']), outcome=outcome, submitted_at=submitted_at)
        self._update_recheck(learner_id=str(session['learner_id']), published_question_id=str(item['published_question_id']), attempt_id=attempt_id, outcome=outcome, submitted_at=submitted_at)
        self._update_session_score(session_id, submitted_at)
        self._update_daily_activity(str(session['learner_id']), outcome, submitted_at, session_id)
        self._event(str(session['learner_id']), session_id, 'attempt_submitted', {'attempt_id': attempt_id, 'ordinal': ordinal, 'outcome': outcome, 'published_question_id': item['published_question_id']})
        self.connection.commit()
        return dict(self.connection.execute('SELECT * FROM runtime_attempts WHERE attempt_id=?', (attempt_id,)).fetchone())

    def _update_mastery(self, *, learner_id: str, concept_id: str, outcome: str, submitted_at: str) -> None:
        row = self.connection.execute('SELECT * FROM runtime_concept_mastery WHERE learner_id=? AND concept_id=?', (learner_id, concept_id)).fetchone()
        attempts = int(row['attempts']) if row else 0
        correct = int(row['correct']) if row else 0
        incorrect = int(row['incorrect']) if row else 0
        skipped = int(row['skipped']) if row else 0
        attempts += 1
        if outcome == 'correct':
            correct += 1
        elif outcome in {'incorrect', 'timeout'}:
            incorrect += 1
        else:
            skipped += 1
        mastery_score = (correct + 1.0) / (attempts + 2.0)
        uncertainty = 1.0 / math.sqrt(attempts + 1.0)
        base = _parse_time(submitted_at)
        if outcome == 'correct':
            interval_days = min(30, max(2, 2 ** min(correct, 4)))
        else:
            interval_days = 1
        next_review_at = _iso(base + timedelta(days=interval_days))
        self.connection.execute('\n                    INSERT OR REPLACE INTO runtime_concept_mastery\n                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n                    ', (learner_id, concept_id, attempts, correct, incorrect, skipped, mastery_score, uncertainty, submitted_at, next_review_at))

    def _update_recheck(self, *, learner_id: str, published_question_id: str, attempt_id: str, outcome: str, submitted_at: str) -> None:
        if outcome == 'correct':
            self.connection.execute("\n                        UPDATE runtime_recheck_queue SET status='completed', updated_at=?\n                        WHERE learner_id=? AND published_question_id=? AND status='pending'\n                        ", (submitted_at, learner_id, published_question_id))
            return
        due_at = _iso(_parse_time(submitted_at) + timedelta(days=1))
        priority = 120 if outcome == 'timeout' else 100
        self.connection.execute("\n                    INSERT OR REPLACE INTO runtime_recheck_queue\n                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)\n                    ", (learner_id, published_question_id, attempt_id, due_at, priority, outcome, submitted_at))

    def _update_session_score(self, session_id: str, now: str) -> None:
        counts = self.connection.execute("\n                    SELECT COUNT(*) AS attempts, SUM(CASE WHEN outcome='correct' THEN 1 ELSE 0 END) AS correct\n                    FROM runtime_attempts WHERE session_id=?\n                    ", (session_id,)).fetchone()
        item_count = int(self.connection.execute('SELECT item_count FROM runtime_sessions WHERE session_id=?', (session_id,)).fetchone()[0])
        attempt_count = int(counts['attempts'] or 0)
        correct_count = int(counts['correct'] or 0)
        status = 'completed' if attempt_count >= item_count else 'active'
        completed_at = now if status == 'completed' else None
        self.connection.execute('\n                    UPDATE runtime_sessions\n                    SET status=?, completed_at=?, correct_count=?, attempt_count=?\n                    WHERE session_id=?\n                    ', (status, completed_at, correct_count, attempt_count, session_id))

    def _update_daily_activity(self, learner_id: str, outcome: str, submitted_at: str, session_id: str) -> None:
        activity_date = _parse_time(submitted_at).date().isoformat()
        completed = int(self.connection.execute("SELECT status='completed' FROM runtime_sessions WHERE session_id=?", (session_id,)).fetchone()[0])
        row = self.connection.execute('SELECT * FROM runtime_daily_activity WHERE learner_id=? AND activity_date=?', (learner_id, activity_date)).fetchone()
        attempts = int(row['attempts']) if row else 0
        correct = int(row['correct']) if row else 0
        completed_sessions = int(row['completed_sessions']) if row else 0
        attempts += 1
        correct += int(outcome == 'correct')
        if completed:
            previously_counted = self.connection.execute("\n                        SELECT COUNT(*) FROM runtime_events\n                        WHERE session_id=? AND event_type='session_completion_counted'\n                        ", (session_id,)).fetchone()[0]
            if not previously_counted:
                completed_sessions += 1
                self._event(learner_id, session_id, 'session_completion_counted', {'activity_date': activity_date})
        self.connection.execute('INSERT OR REPLACE INTO runtime_daily_activity VALUES (?, ?, ?, ?, ?)', (learner_id, activity_date, attempts, correct, completed_sessions))
