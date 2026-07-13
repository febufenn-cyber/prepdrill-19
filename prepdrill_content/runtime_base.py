"""Shared Phase 2 runtime database and readiness authorization operations."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .ids import canonical_json, sha256_text, stable_id
from .models import utc_now
from .runtime_models import RUNTIME_SCHEMA_SQL


class RuntimeBase:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.initialise()

    @classmethod
    def open(cls, path: str | Path = ":memory:") -> "RuntimeBase":
        connection = sqlite3.connect(str(path))
        return cls(connection)

    def initialise(self) -> None:
        self.connection.executescript(RUNTIME_SCHEMA_SQL)
        self.connection.commit()

    def corpus_fingerprint(self) -> str:
        rows = self.connection.execute(
            """
            SELECT qr.revision_id, qr.semantic_hash
            FROM question_revisions qr
            JOIN (
              SELECT question_id, MAX(version) AS version
              FROM question_revisions GROUP BY question_id
            ) latest ON latest.question_id=qr.question_id AND latest.version=qr.version
            ORDER BY qr.question_id
            """
        )
        return sha256_text("\n".join(f"{row[0]}:{row[1]}" for row in rows))

    def authorize_launch(self, evaluation_id: str, *, owner: str, reason: str) -> str:
        owner = owner.strip()
        reason = reason.strip()
        if not owner or not reason:
            raise ValueError("owner and reason are required")
        row = self.connection.execute(
            "SELECT corpus_fingerprint, passed, report_json FROM readiness_gate_evaluations WHERE evaluation_id=?",
            (evaluation_id,),
        ).fetchone()
        if not row:
            raise ValueError("unknown readiness gate evaluation")
        if int(row["passed"]) != 1:
            raise ValueError("readiness gate evaluation did not pass")
        report = json.loads(row["report_json"])
        if report.get("passed") is not True:
            raise ValueError("readiness gate report is not explicitly passed")
        current = self.corpus_fingerprint()
        if str(row["corpus_fingerprint"]) != current:
            raise ValueError("readiness gate evaluation is stale")
        authorization_id = stable_id("authorization", evaluation_id, current, owner)
        self.connection.execute("UPDATE runtime_launch_authorizations SET active=0, revoked_at=? WHERE active=1", (utc_now(),))
        self.connection.execute(
            "INSERT OR REPLACE INTO runtime_launch_authorizations VALUES (?, ?, ?, ?, ?, 1, ?, NULL)",
            (authorization_id, evaluation_id, current, owner, reason, utc_now()),
        )
        self.connection.commit()
        return authorization_id

    def revoke_launch(self, *, owner: str, reason: str) -> int:
        owner = owner.strip()
        reason = reason.strip()
        if not owner or not reason:
            raise ValueError("owner and reason are required")
        rows = list(self.connection.execute("SELECT authorization_id FROM runtime_launch_authorizations WHERE active=1"))
        self.connection.execute(
            "UPDATE runtime_launch_authorizations SET active=0, revoked_at=? WHERE active=1",
            (utc_now(),),
        )
        for row in rows:
            self._event(None, None, "launch_revoked", {"authorization_id": row[0], "owner": owner, "reason": reason})
        self.connection.commit()
        return len(rows)

    def current_authorization(self) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT authorization_id, evaluation_id, corpus_fingerprint, owner, reason, authorized_at
            FROM runtime_launch_authorizations WHERE active=1
            ORDER BY authorized_at DESC LIMIT 1
            """
        ).fetchone()
        if not row:
            raise PermissionError("Phase 2 runtime is locked: no active launch authorization")
        evaluation = self.connection.execute(
            "SELECT passed, corpus_fingerprint, report_json FROM readiness_gate_evaluations WHERE evaluation_id=?",
            (row["evaluation_id"],),
        ).fetchone()
        if not evaluation or int(evaluation["passed"]) != 1:
            raise PermissionError("Phase 2 runtime is locked: readiness evaluation is not passed")
        report = json.loads(evaluation["report_json"])
        if report.get("passed") is not True:
            raise PermissionError("Phase 2 runtime is locked: readiness report is not explicitly passed")
        current = self.corpus_fingerprint()
        if current != str(row["corpus_fingerprint"]) or current != str(evaluation["corpus_fingerprint"]):
            raise PermissionError("Phase 2 runtime is locked: corpus changed after authorization")
        return dict(row)

    def ensure_learner(self, learner_id: str, *, timezone: str = "UTC") -> None:
        learner_id = learner_id.strip()
        if not learner_id:
            raise ValueError("learner_id is required")
        self.connection.execute(
            "INSERT OR IGNORE INTO runtime_learners VALUES (?, ?, ?)",
            (learner_id, timezone, utc_now()),
        )
        self.connection.commit()

    def _event(self, learner_id: str | None, session_id: str | None, event_type: str, payload: dict[str, Any]) -> str:
        created_at = utc_now()
        event_id = stable_id("event", event_type, learner_id or "", session_id or "", canonical_json(payload), created_at)
        self.connection.execute(
            "INSERT INTO runtime_events VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, learner_id, session_id, event_type, canonical_json(payload), created_at),
        )
        return event_id
