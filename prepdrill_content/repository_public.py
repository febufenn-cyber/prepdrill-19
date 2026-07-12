"""Learner-safe read facade over immutable published snapshots."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

class PublicContentRepository:
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
