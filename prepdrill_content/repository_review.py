"""Review, validation, publication, readiness, and taxonomy operations."""
from __future__ import annotations

import json
from typing import Any

from .ids import canonical_json, content_hash, stable_id
from .models import utc_now
from .validators import ValidationReport, validate_question

class ReviewRepositoryMixin:
    def update_review_state(self, revision_id: str, *, actor: str, action: str, reason: str, workflow_state: str | None = None, issue_state: str | None = None, validation_tier: str | None = None, verification: dict[str, Any] | None = None) -> dict[str, Any]:
        before = self.get_revision(revision_id)
        after = dict(before)
        if workflow_state is not None:
            after["workflow_state"] = workflow_state
        if issue_state is not None:
            after["issue_state"] = issue_state
        if validation_tier is not None:
            after["validation_tier"] = validation_tier
        if verification is not None:
            merged = dict(after.get("verification") or {})
            merged.update(verification)
            after["verification"] = merged
        self.connection.execute("UPDATE question_revisions SET content_json=? WHERE revision_id=?", (canonical_json(after), revision_id))
        event_id = stable_id("review", revision_id, action, utc_now(), actor)
        self.connection.execute(
            "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, revision_id, actor, action, reason, canonical_json(before), canonical_json(after), utc_now()),
        )
        self.connection.commit()
        return after

    def register_asset(self, *, asset_id: str, checksum: str, media_type: str, storage_ref: str, status: str = "verified") -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO assets VALUES (?, ?, ?, ?, ?, ?)",
            (asset_id, checksum, media_type, storage_ref, status, utc_now()),
        )
        self.connection.commit()

    def register_context(self, *, context_id: str, content: dict[str, Any], status: str = "verified") -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO shared_contexts VALUES (?, ?, ?, ?, ?)",
            (context_id, canonical_json(content), content_hash(content), status, utc_now()),
        )
        self.connection.commit()

    def validate_revision(self, revision_id: str, *, publication: bool = False) -> ValidationReport:
        record = self.get_revision(revision_id)
        known_assets = {str(row[0]) for row in self.connection.execute("SELECT asset_id FROM assets WHERE status='verified'")}
        known_contexts = {str(row[0]) for row in self.connection.execute("SELECT context_id FROM shared_contexts WHERE status='verified'")}
        report = validate_question(record, publication=publication, known_assets=known_assets, known_contexts=known_contexts)
        run_id = stable_id("validation", revision_id, "publish" if publication else "normal", utc_now())
        self.connection.execute(
            "INSERT INTO validation_runs VALUES (?, ?, ?, ?, ?)",
            (run_id, revision_id, int(publication), int(report.ok), utc_now()),
        )
        for index, finding in enumerate(report.findings):
            finding_id = stable_id("finding", run_id, str(index), finding.code, finding.path)
            self.connection.execute(
                "INSERT INTO validation_findings VALUES (?, ?, ?, ?, ?, ?)",
                (finding_id, run_id, finding.level, finding.code, finding.path, finding.message),
            )
        self.connection.commit()
        return report

    def scan_duplicate_fingerprints(self) -> int:
        revisions = list(self.connection.execute(
            "SELECT revision_id, exact_fingerprint, near_fingerprint FROM question_revisions ORDER BY revision_id"
        ))
        inserted = 0
        for index, left in enumerate(revisions):
            for right in revisions[index + 1 :]:
                duplicate_type = None
                confidence = 0.0
                if left[1] == right[1]:
                    duplicate_type = "exact_content"
                    confidence = 1.0
                elif left[2] == right[2]:
                    duplicate_type = "near_token_set"
                    confidence = 0.95
                if duplicate_type:
                    candidate_id = stable_id("dup", str(left[0]), str(right[0]), duplicate_type)
                    cursor = self.connection.execute(
                        "INSERT OR IGNORE INTO duplicate_candidates VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (candidate_id, left[0], right[0], duplicate_type, confidence, "pending", utc_now()),
                    )
                    inserted += cursor.rowcount
        self.connection.commit()
        return inserted

    def publish(self, revision_id: str, *, actor: str, reason: str) -> str:
        report = self.validate_revision(revision_id, publication=True)
        if not report.ok:
            codes = ", ".join(sorted(report.codes()))
            raise ValueError(f"revision is not publishable: {codes}")
        record = self.get_revision(revision_id)
        question_id = str(record["question_id"])
        existing = self.connection.execute(
            "SELECT published_question_id FROM published_snapshots WHERE revision_id=?", (revision_id,)
        ).fetchone()
        if existing:
            return str(existing[0])
        self.connection.execute(
            "UPDATE published_snapshots SET retired_at=? WHERE question_id=? AND retired_at IS NULL",
            (utc_now(), question_id),
        )
        payload = dict(record)
        payload["workflow_state"] = "published"
        public_id = stable_id("pub", question_id, revision_id)
        self.connection.execute(
            "INSERT INTO published_snapshots VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (public_id, question_id, revision_id, canonical_json(payload), content_hash(payload), utc_now()),
        )
        event_id = stable_id("review", revision_id, "publish", utc_now(), actor)
        self.connection.execute(
            "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, revision_id, actor, "publish", reason, canonical_json(record), canonical_json(payload), utc_now()),
        )
        self.connection.commit()
        return public_id

    def unpublish(self, question_id: str, *, actor: str, reason: str) -> int:
        rows = list(self.connection.execute(
            "SELECT revision_id FROM published_snapshots WHERE question_id=? AND retired_at IS NULL", (question_id,)
        ))
        self.connection.execute(
            "UPDATE published_snapshots SET retired_at=? WHERE question_id=? AND retired_at IS NULL", (utc_now(), question_id)
        )
        for row in rows:
            event_id = stable_id("review", str(row[0]), "unpublish", utc_now(), actor)
            self.connection.execute(
                "INSERT INTO review_events VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)",
                (event_id, row[0], actor, "unpublish", reason, utc_now()),
            )
        self.connection.commit()
        return len(rows)

    def readiness_report(self) -> dict[str, Any]:
        rows = [json.loads(row[0]) for row in self.connection.execute("SELECT content_json FROM question_revisions")]
        def count_by(field: str) -> dict[str, int]:
            result: dict[str, int] = {}
            for row in rows:
                value = str(row.get(field, "<missing>"))
                result[value] = result.get(value, 0) + 1
            return dict(sorted(result.items()))
        blockers: dict[str, int] = {}
        for row in rows:
            report = validate_question(row, publication=True)
            for finding in report.errors:
                blockers[finding.code] = blockers.get(finding.code, 0) + 1
        return {
            "total_revisions": len(rows),
            "canonical_questions": int(self.connection.execute("SELECT COUNT(*) FROM canonical_questions").fetchone()[0]),
            "published_active": int(self.connection.execute("SELECT COUNT(*) FROM published_snapshots WHERE retired_at IS NULL").fetchone()[0]),
            "by_tier": count_by("validation_tier"),
            "by_unit": count_by("unit_id"),
            "by_type": count_by("question_type"),
            "by_workflow": count_by("workflow_state"),
            "by_issue": count_by("issue_state"),
            "publication_blockers": dict(sorted(blockers.items())),
            "duplicate_candidates": int(self.connection.execute("SELECT COUNT(*) FROM duplicate_candidates").fetchone()[0]),
        }

    def load_taxonomy(self, payload: dict[str, Any]) -> int:
        version = str(payload["version"])
        count = 0
        for unit in payload.get("units", []):
            self._insert_taxonomy_node(unit["unit_id"], None, "unit", unit["label"], version)
            count += 1
            for topic in unit.get("topics", []):
                self._insert_taxonomy_node(topic["topic_id"], unit["unit_id"], "topic", topic["label"], version)
                count += 1
                for concept in topic.get("concepts", []):
                    self._insert_taxonomy_node(concept["concept_id"], topic["topic_id"], "concept", concept["label"], version)
                    count += 1
        self.connection.commit()
        return count

    def _insert_taxonomy_node(self, node_id: str, parent_id: str | None, node_type: str, label: str, version: str) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO taxonomy_nodes(node_id,parent_id,node_type,label,ontology_version,active) VALUES (?, ?, ?, ?, ?, 1)",
            (node_id, parent_id, node_type, label, version),
        )
