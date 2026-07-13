"""Grounded explanations, diagnosis, and streak insights."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .ids import canonical_json, content_hash, stable_id
from .models import utc_now


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class RuntimeInsightsMixin:
    def explain_attempt(self, attempt_id: str) -> dict[str, Any]:
        stored = self.connection.execute('SELECT explanation_json FROM runtime_explanations WHERE attempt_id=?', (attempt_id,)).fetchone()
        if stored:
            return json.loads(stored[0])
        row = self.connection.execute('\n                    SELECT ra.*, ps.revision_id, ps.payload_json\n                    FROM runtime_attempts ra\n                    JOIN published_snapshots ps ON ps.published_question_id=ra.published_question_id\n                    WHERE ra.attempt_id=?\n                    ', (attempt_id,)).fetchone()
        if not row:
            raise KeyError(attempt_id)
        payload = json.loads(row['payload_json'])
        reviewed = payload.get('reviewed_explanation')
        if not isinstance(reviewed, dict):
            reviewed = (payload.get('metadata') or {}).get('reviewed_explanation')
        source_refs = reviewed.get('source_refs') if isinstance(reviewed, dict) else None
        grounded = isinstance(reviewed, dict) and isinstance(reviewed.get('summary'), str) and bool(reviewed.get('summary', '').strip()) and isinstance(reviewed.get('reviewed_at'), str) and isinstance(source_refs, list) and bool(source_refs)
        if grounded:
            explanation = {'attempt_id': attempt_id, 'status': 'grounded', 'outcome': row['outcome'], 'selected_option_id': row['selected_option_id'], 'correct_option_id': row['correct_option_id'], 'summary': reviewed['summary'], 'why_correct': reviewed.get('why_correct'), 'why_others_wrong': reviewed.get('why_others_wrong', {}), 'source_refs': source_refs, 'reviewed_at': reviewed['reviewed_at'], 'revision_id': row['revision_id']}
        else:
            explanation = {'attempt_id': attempt_id, 'status': 'unavailable', 'outcome': row['outcome'], 'selected_option_id': row['selected_option_id'], 'correct_option_id': row['correct_option_id'], 'message': 'No reviewed, source-grounded explanation is available for this revision.', 'revision_id': row['revision_id']}
        grounding_hash = content_hash({'revision_id': row['revision_id'], 'payload_hash': row['payload_hash'], 'explanation': explanation})
        explanation_id = stable_id('explanation', attempt_id, grounding_hash)
        self.connection.execute('INSERT INTO runtime_explanations VALUES (?, ?, ?, ?, ?, ?)', (explanation_id, attempt_id, explanation['status'], canonical_json(explanation), grounding_hash, utc_now()))
        self.connection.commit()
        return explanation

    def diagnose(self, learner_id: str, *, target_count: int=3, now: str | None=None) -> dict[str, Any]:
        point = now or utc_now()
        concepts = {str(row[0]) for row in self.connection.execute("\n                        SELECT DISTINCT json_extract(payload_json, '$.primary_concept_id')\n                        FROM published_snapshots WHERE retired_at IS NULL\n                        ") if row[0]}
        mastery_rows = {str(row['concept_id']): dict(row) for row in self.connection.execute('SELECT * FROM runtime_concept_mastery WHERE learner_id=?', (learner_id,))}
        heatmap: list[dict[str, Any]] = []
        for concept_id in sorted(concepts):
            row = mastery_rows.get(concept_id)
            score = float(row['mastery_score']) if row else 0.5
            attempts = int(row['attempts']) if row else 0
            due = bool(row and str(row['next_review_at']) <= point)
            weakness = 1.0 - score + (0.1 if due else 0.0) + (0.05 if attempts == 0 else 0.0)
            heatmap.append({'concept_id': concept_id, 'mastery_score': score, 'attempts': attempts, 'due': due, 'weakness': round(weakness, 6)})
        heatmap.sort(key=lambda item: (-item['weakness'], item['concept_id']))
        outcomes = {str(row[0]): int(row[1]) for row in self.connection.execute('SELECT outcome, COUNT(*) FROM runtime_attempts WHERE learner_id=? GROUP BY outcome', (learner_id,))}
        due_rechecks = int(self.connection.execute("SELECT COUNT(*) FROM runtime_recheck_queue WHERE learner_id=? AND status='pending' AND due_at<=?", (learner_id, point)).fetchone()[0])
        return {'learner_id': learner_id, 'weakness_heatmap': heatmap, 'target_concepts': [item['concept_id'] for item in heatmap[:target_count]], 'outcomes': outcomes, 'due_rechecks': due_rechecks}

    def streak(self, learner_id: str) -> dict[str, Any]:
        active_dates = [str(row[0]) for row in self.connection.execute('\n                        SELECT activity_date FROM runtime_daily_activity\n                        WHERE learner_id=? AND attempts>0 ORDER BY activity_date DESC\n                        ', (learner_id,))]
        if not active_dates:
            return {'learner_id': learner_id, 'current_streak': 0, 'active_days': 0}
        current = 1
        for previous, following in zip(active_dates, active_dates[1:]):
            if (_parse_time(previous + 'T00:00:00+00:00').date() - _parse_time(following + 'T00:00:00+00:00').date()).days == 1:
                current += 1
            else:
                break
        return {'learner_id': learner_id, 'current_streak': current, 'active_days': len(active_dates)}
