"""Immutable raw import, canonical revision, and evidence operations."""
from __future__ import annotations

import json
from typing import Any

from .ids import canonical_json, content_hash, exact_fingerprint, near_fingerprint, stable_id
from .models import semantic_payload, utc_now

class ImportRepositoryMixin:
    def create_or_get_batch(self, *, adapter_name: str, adapter_version: str, source_document_id: str, source_checksum: str) -> tuple[str, bool]:
        row = self.connection.execute(
            "SELECT import_batch_id FROM import_batches WHERE adapter_name=? AND adapter_version=? AND source_document_id=? AND source_checksum=?",
            (adapter_name, adapter_version, source_document_id, source_checksum),
        ).fetchone()
        if row:
            return str(row[0]), False
        batch_id = stable_id("batch", adapter_name, adapter_version, source_document_id, source_checksum)
        self.connection.execute(
            "INSERT INTO import_batches VALUES (?, ?, ?, ?, ?, ?, ?)",
            (batch_id, adapter_name, adapter_version, source_document_id, source_checksum, "running", utc_now()),
        )
        self.connection.commit()
        return batch_id, True

    def complete_batch(self, batch_id: str) -> None:
        self.connection.execute("UPDATE import_batches SET status='completed' WHERE import_batch_id=?", (batch_id,))
        self.connection.commit()

    def store_raw(self, *, batch_id: str, source_locator: str, raw: dict[str, Any]) -> tuple[str, bool]:
        raw_json = canonical_json(raw)
        checksum = content_hash(raw)
        row = self.connection.execute(
            "SELECT raw_record_id FROM raw_records WHERE import_batch_id=? AND source_locator=? AND raw_checksum=?",
            (batch_id, source_locator, checksum),
        ).fetchone()
        if row:
            return str(row[0]), False
        raw_id = stable_id("raw", batch_id, source_locator, checksum)
        self.connection.execute(
            "INSERT INTO raw_records VALUES (?, ?, ?, ?, ?, ?)",
            (raw_id, batch_id, source_locator, raw_json, checksum, utc_now()),
        )
        self.connection.commit()
        return raw_id, True

    def upsert_revision(self, record: dict[str, Any]) -> tuple[str, int, bool]:
        question_id = str(record["question_id"])
        semantic_hash = content_hash(semantic_payload(record))
        row = self.connection.execute(
            "SELECT revision_id, version FROM question_revisions WHERE question_id=? AND semantic_hash=?",
            (question_id, semantic_hash),
        ).fetchone()
        if row:
            revision_id = str(row[0])
            self._attach_evidence(revision_id, record)
            self.connection.commit()
            return revision_id, int(row[1]), False
        previous = self.connection.execute(
            "SELECT revision_id, version FROM question_revisions WHERE question_id=? ORDER BY version DESC LIMIT 1",
            (question_id,),
        ).fetchone()
        version = int(previous[1]) + 1 if previous else 1
        previous_id = str(previous[0]) if previous else None
        revision_id = stable_id("rev", question_id, str(version), semantic_hash)
        self.connection.execute("INSERT OR IGNORE INTO canonical_questions VALUES (?, ?)", (question_id, utc_now()))
        payload = dict(record)
        payload["version"] = version
        payload["revision_id"] = revision_id
        self.connection.execute(
            "INSERT INTO question_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision_id,
                question_id,
                version,
                canonical_json(payload),
                semantic_hash,
                exact_fingerprint(payload),
                near_fingerprint(payload),
                utc_now(),
                previous_id,
            ),
        )
        self._attach_evidence(revision_id, payload)
        self.connection.commit()
        return revision_id, version, True

    def _attach_evidence(self, revision_id: str, record: dict[str, Any]) -> None:
        provenance = record.get("provenance") or {}
        source_document_id = str(provenance.get("source_document_id") or "")
        source_locator = str(provenance.get("source_locator") or "")
        if source_document_id and source_locator:
            source_link_id = stable_id("src", revision_id, source_document_id, source_locator)
            self.connection.execute(
                "INSERT OR IGNORE INTO source_links VALUES (?, ?, ?, ?, ?, ?)",
                (source_link_id, revision_id, source_document_id, source_locator, canonical_json(provenance), utc_now()),
            )
        evidence_type = provenance.get("answer_evidence")
        if evidence_type:
            claim_id = stable_id("claim", revision_id, str(record.get("correct_option_id")), str(evidence_type), str(provenance.get("answer_key_reference") or ""))
            self.connection.execute(
                "INSERT OR IGNORE INTO answer_claims VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    claim_id, revision_id, str(record.get("correct_option_id")), str(evidence_type),
                    provenance.get("answer_key_reference"),
                    "accepted" if evidence_type != "unverified" else "unverified", utc_now(),
                ),
            )

    def get_revision(self, revision_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT content_json FROM question_revisions WHERE revision_id=?", (revision_id,)).fetchone()
        if not row:
            raise KeyError(revision_id)
        return json.loads(row[0])

    def latest_revision(self, question_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT content_json FROM question_revisions WHERE question_id=? ORDER BY version DESC LIMIT 1", (question_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None
