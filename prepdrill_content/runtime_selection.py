"""Deterministic Phase 2 session selection and learner-safe reads."""
from __future__ import annotations

import json
import math
from typing import Any

from .ids import sha256_text, stable_id
from .models import utc_now
from .runtime_models import SESSION_MODES


class RuntimeSelectionMixin:
    def _published_candidates(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in self.connection.execute('\n                    SELECT published_question_id, question_id, revision_id, payload_json, payload_hash\n                    FROM published_snapshots WHERE retired_at IS NULL\n                    ORDER BY published_question_id\n                    '):
            payload = json.loads(row['payload_json'])
            result.append({'published_question_id': str(row['published_question_id']), 'question_id': str(row['question_id']), 'revision_id': str(row['revision_id']), 'payload_hash': str(row['payload_hash']), 'unit_id': str(payload.get('unit_id') or '<missing>'), 'concept_id': str(payload.get('primary_concept_id') or '<missing>'), 'question_type': str(payload.get('question_type') or '<missing>'), 'payload': payload})
        return result

    def _selection_state(self, learner_id: str, now: str) -> tuple[dict[str, dict[str, Any]], set[str], dict[str, dict[str, Any]]]:
        mastery = {str(row['concept_id']): dict(row) for row in self.connection.execute('SELECT * FROM runtime_concept_mastery WHERE learner_id=?', (learner_id,))}
        attempted = {str(row[0]) for row in self.connection.execute('SELECT published_question_id FROM runtime_attempts WHERE learner_id=?', (learner_id,))}
        due = {str(row['published_question_id']): dict(row) for row in self.connection.execute("\n                        SELECT * FROM runtime_recheck_queue\n                        WHERE learner_id=? AND status='pending' AND due_at<=?\n                        ", (learner_id, now))}
        return (mastery, attempted, due)

    def _candidate_score(self, candidate: dict[str, Any], *, mode: str, seed: str, mastery: dict[str, dict[str, Any]], attempted: set[str], due: dict[str, dict[str, Any]]) -> tuple[float, str, str]:
        published_id = candidate['published_question_id']
        concept_id = candidate['concept_id']
        state = mastery.get(concept_id)
        mastery_score = float(state['mastery_score']) if state else 0.5
        attempts = int(state['attempts']) if state else 0
        due_item = due.get(published_id)
        if mode == 'recheck' and (not due_item):
            return (-math.inf, 'not_due', '')
        score = (1.0 - mastery_score) * 100.0
        reason = 'weak_concept'
        if not state:
            score += 25.0
            reason = 'unseen_concept'
        if published_id in attempted:
            score -= 15.0 + min(attempts, 10)
            reason = 'weak_concept_repeat'
        if due_item:
            score += 1000.0 + float(due_item['priority'])
            reason = 'due_recheck'
        if mode == 'mixed':
            score = 50.0 + (10.0 if not state else 0.0) + (1000.0 if due_item else 0.0)
            reason = 'mixed_coverage' if not due_item else 'due_recheck'
        tie = sha256_text(f'{seed}\x1f{published_id}')
        return (score, reason, tie)

    def create_session(self, learner_id: str, *, size: int=10, seed: str='daily', mode: str='adaptive', timezone_name: str='UTC', now: str | None=None) -> dict[str, Any]:
        if mode not in SESSION_MODES:
            raise ValueError(f'unsupported session mode: {mode}')
        if size < 1 or size > 100:
            raise ValueError('size must be between 1 and 100')
        authorization = self.current_authorization()
        self.ensure_learner(learner_id, timezone=timezone_name)
        selected_at = now or utc_now()
        mastery, attempted, due = self._selection_state(learner_id, selected_at)
        candidates = self._published_candidates()
        scored: list[tuple[float, str, str, dict[str, Any]]] = []
        for candidate in candidates:
            score, reason, tie = self._candidate_score(candidate, mode=mode, seed=seed, mastery=mastery, attempted=attempted, due=due)
            if score != -math.inf:
                scored.append((score, reason, tie, candidate))
        scored.sort(key=lambda item: (-item[0], item[2], item[3]['published_question_id']))
        chosen = scored[:size]
        if not chosen:
            raise ValueError('no eligible published questions are available')
        session_id = stable_id('session', learner_id, str(authorization['authorization_id']), mode, seed, selected_at)
        existing = self.connection.execute('SELECT session_id FROM runtime_sessions WHERE session_id=?', (session_id,)).fetchone()
        if existing:
            return self.get_session(session_id)
        self.connection.execute("INSERT INTO runtime_sessions VALUES (?, ?, ?, ?, ?, ?, 'active', ?, NULL, 0, 0, ?)", (session_id, learner_id, authorization['authorization_id'], mode, size, seed, selected_at, len(chosen)))
        for ordinal, (_, reason, _, candidate) in enumerate(chosen):
            self.connection.execute('INSERT INTO runtime_session_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (session_id, ordinal, candidate['published_question_id'], candidate['question_id'], candidate['revision_id'], candidate['unit_id'], candidate['concept_id'], candidate['question_type'], reason, candidate['payload_hash']))
        self._event(learner_id, session_id, 'session_created', {'mode': mode, 'requested_size': size, 'item_count': len(chosen), 'seed': seed, 'authorization_id': authorization['authorization_id']})
        self.connection.commit()
        return self.get_session(session_id)

    def get_session(self, session_id: str, *, include_answers: bool=False) -> dict[str, Any]:
        session = self.connection.execute('SELECT * FROM runtime_sessions WHERE session_id=?', (session_id,)).fetchone()
        if not session:
            raise KeyError(session_id)
        items: list[dict[str, Any]] = []
        for row in self.connection.execute('\n                    SELECT rsi.*, ps.payload_json\n                    FROM runtime_session_items rsi\n                    JOIN published_snapshots ps ON ps.published_question_id=rsi.published_question_id\n                    WHERE rsi.session_id=? ORDER BY rsi.ordinal\n                    ', (session_id,)):
            payload = json.loads(row['payload_json'])
            if not include_answers:
                payload.pop('correct_option_id', None)
                payload.pop('reviewed_explanation', None)
                metadata = dict(payload.get('metadata') or {})
                metadata.pop('reviewed_explanation', None)
                payload['metadata'] = metadata
            items.append({'ordinal': int(row['ordinal']), 'published_question_id': row['published_question_id'], 'question_id': row['question_id'], 'revision_id': row['revision_id'], 'selection_reason': row['selection_reason'], 'payload_hash': row['payload_hash'], 'question': payload})
        result = dict(session)
        result['items'] = items
        return result
