"""Shared corpus snapshot operations for readiness repositories."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .ids import sha256_text
from .readiness_models import READINESS_SCHEMA_SQL


class ReadinessBase:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.initialise()

    def initialise(self) -> None:
        self.connection.executescript(READINESS_SCHEMA_SQL)
        self.connection.commit()

    def _latest_revisions(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT qr.revision_id, qr.question_id, qr.version, qr.content_json,
                   qr.semantic_hash
            FROM question_revisions qr
            JOIN (
              SELECT question_id, MAX(version) AS version
              FROM question_revisions GROUP BY question_id
            ) latest
              ON latest.question_id = qr.question_id AND latest.version = qr.version
            ORDER BY qr.question_id
            """
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["content_json"])
            result.append({
                "revision_id": str(row["revision_id"]),
                "question_id": str(row["question_id"]),
                "version": int(row["version"]),
                "semantic_hash": str(row["semantic_hash"]),
                "unit_id": str(payload.get("unit_id", "<missing>")),
                "question_type": str(payload.get("question_type", "<missing>")),
                "validation_tier": str(payload.get("validation_tier", "<missing>")),
                "payload": payload,
            })
        return result

    def corpus_fingerprint(self) -> str:
        material = [
            f"{row['revision_id']}:{row['semantic_hash']}"
            for row in self._latest_revisions()
        ]
        return sha256_text("\n".join(material))
