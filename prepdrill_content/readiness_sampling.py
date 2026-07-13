"""Audit sampling, evidence ingestion, and duplicate adjudication."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from .ids import canonical_json, sha256_text, stable_id
from .models import utc_now
from .readiness_models import DUPLICATE_DECISIONS, REQUIRED_REVIEW_FIELDS, REVIEW_VERDICTS


class ReadinessSamplingMixin:
    @staticmethod
    def _stable_order(seed: str, revision_id: str) -> str:
        return sha256_text(f"{seed}\x1f{revision_id}")

    @classmethod
    def _stratified_sample(
        cls, population: Iterable[dict[str, Any]], target: int, seed: str
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in population:
            key = "|".join((item["unit_id"], item["question_type"], item["validation_tier"]))
            groups.setdefault(key, []).append(item)
        for items in groups.values():
            items.sort(key=lambda item: cls._stable_order(seed, item["revision_id"]))

        selected: list[dict[str, Any]] = []
        keys = sorted(groups)
        while len(selected) < target:
            progressed = False
            for key in keys:
                if groups[key] and len(selected) < target:
                    item = groups[key].pop(0)
                    item = dict(item)
                    item["stratum_key"] = key
                    selected.append(item)
                    progressed = True
            if not progressed:
                break
        return selected

    def create_audit_run(
        self,
        *,
        name: str,
        sample_target: int = 250,
        seed: str = "phase-1.5",
        criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not name.strip():
            raise ValueError("name is required")
        if sample_target < 1:
            raise ValueError("sample_target must be positive")
        population = self._latest_revisions()
        fingerprint = self.corpus_fingerprint()
        run_id = stable_id("audit", name, str(sample_target), seed, fingerprint)
        existing = self.connection.execute(
            "SELECT * FROM readiness_audit_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if existing:
            return dict(existing)

        selected = self._stratified_sample(
            population, min(sample_target, len(population)), seed
        )
        status = "open" if len(selected) >= sample_target else "undersized"
        self.connection.execute(
            "INSERT INTO readiness_audit_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                run_id, name.strip(), sample_target, seed, fingerprint, len(population),
                status, canonical_json(criteria or {}), utc_now(),
            ),
        )
        now = utc_now()
        for ordinal, item in enumerate(selected, start=1):
            self.connection.execute(
                "INSERT INTO readiness_sample_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, item["revision_id"], item["question_id"], item["unit_id"],
                    item["question_type"], item["validation_tier"], item["stratum_key"],
                    ordinal, item["semantic_hash"], now,
                ),
            )
        self.connection.commit()
        return dict(self.connection.execute(
            "SELECT * FROM readiness_audit_runs WHERE run_id=?", (run_id,)
        ).fetchone())

    def _require_sample_item(self, run_id: str, revision_id: str) -> None:
        row = self.connection.execute(
            "SELECT 1 FROM readiness_sample_items WHERE run_id=? AND revision_id=?",
            (run_id, revision_id),
        ).fetchone()
        if not row:
            raise ValueError(f"revision is not in the audit sample: {revision_id}")

    def record_review(self, run_id: str, review: dict[str, Any]) -> str:
        missing = sorted(REQUIRED_REVIEW_FIELDS - set(review))
        if missing:
            raise ValueError(f"missing review fields: {', '.join(missing)}")
        revision_id = str(review["revision_id"])
        self._require_sample_item(run_id, revision_id)
        verdict = str(review["verdict"])
        if verdict not in REVIEW_VERDICTS:
            raise ValueError(f"invalid verdict: {verdict}")
        seconds = int(review["review_seconds"])
        if seconds < 0:
            raise ValueError("review_seconds cannot be negative")
        reviewer = str(review["reviewer"]).strip()
        if not reviewer:
            raise ValueError("reviewer is required")
        reviewed_at = str(review.get("reviewed_at") or utc_now())
        boolean_fields = (
            "rights_ok", "answer_evidence_ok", "render_ok", "mapping_ok", "provenance_ok"
        )
        for name in boolean_fields:
            if not isinstance(review[name], bool):
                raise ValueError(f"{name} must be a JSON boolean")
        booleans = [int(review[name]) for name in boolean_fields]
        review_id = stable_id(
            "rreview", run_id, revision_id, reviewer, reviewed_at,
            verdict, *(str(value) for value in booleans), str(seconds),
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO readiness_reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                review_id, run_id, revision_id, reviewer, verdict, *booleans, seconds,
                str(review.get("notes") or ""), reviewed_at,
            ),
        )
        self.connection.commit()
        return review_id

    def record_mapping_label(self, run_id: str, label: dict[str, Any]) -> str:
        revision_id = str(label.get("revision_id") or "")
        reviewer = str(label.get("reviewer") or "").strip()
        concept_id = str(label.get("concept_id") or "").strip()
        if not revision_id or not reviewer or not concept_id:
            raise ValueError("revision_id, reviewer and concept_id are required")
        self._require_sample_item(run_id, revision_id)
        recorded_at = str(label.get("recorded_at") or utc_now())
        label_id = stable_id("map", run_id, revision_id, reviewer, concept_id, recorded_at)
        self.connection.execute(
            "INSERT OR IGNORE INTO readiness_mapping_labels VALUES (?, ?, ?, ?, ?, ?)",
            (label_id, run_id, revision_id, reviewer, concept_id, recorded_at),
        )
        self.connection.commit()
        return label_id

    def sample_items(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT s.*, q.content_json
            FROM readiness_sample_items s
            JOIN question_revisions q ON q.revision_id=s.revision_id
            WHERE s.run_id=? ORDER BY s.ordinal
            """, (run_id,)
        )
        return [
            {**{key: row[key] for key in row.keys() if key != "content_json"},
             "content": json.loads(row["content_json"])}
            for row in rows
        ]

    def adjudicate_duplicate(
        self, candidate_id: str, *, reviewer: str, decision: str, reason: str,
        canonical_revision_id: str | None = None,
    ) -> str:
        if decision not in DUPLICATE_DECISIONS:
            raise ValueError(f"invalid duplicate decision: {decision}")
        if not reviewer.strip() or not reason.strip():
            raise ValueError("reviewer and reason are required")
        candidate = self.connection.execute(
            "SELECT * FROM duplicate_candidates WHERE candidate_id=?", (candidate_id,)
        ).fetchone()
        if not candidate:
            raise KeyError(candidate_id)
        allowed = {str(candidate["left_revision_id"]), str(candidate["right_revision_id"])}
        if canonical_revision_id is not None and canonical_revision_id not in allowed:
            raise ValueError("canonical_revision_id must be one of the candidate revisions")
        if decision == "same_question" and canonical_revision_id is None:
            raise ValueError("same_question requires canonical_revision_id")
        status = "dismissed" if decision == "distinct_questions" else "resolved"
        adjudicated_at = utc_now()
        adjudication_id = stable_id(
            "adjudication", candidate_id, reviewer, decision,
            canonical_revision_id or "", reason, adjudicated_at,
        )
        self.connection.execute(
            "INSERT INTO readiness_duplicate_adjudications VALUES (?, ?, ?, ?, ?, ?, ?)",
            (adjudication_id, candidate_id, reviewer, decision, canonical_revision_id, reason, adjudicated_at),
        )
        self.connection.execute(
            "UPDATE duplicate_candidates SET status=? WHERE candidate_id=?",
            (status, candidate_id),
        )
        self.connection.commit()
        return adjudication_id

    @staticmethod
    def _jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
        for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number}: expected JSON object")
            yield value

    def ingest_reviews(self, run_id: str, path: str | Path) -> dict[str, Any]:
        inserted = 0
        errors: list[str] = []
        for index, review in enumerate(self._jsonl(path), start=1):
            try:
                self.record_review(run_id, review)
                inserted += 1
            except Exception as exc:
                errors.append(f"line {index}: {exc}")
        return {"inserted": inserted, "errors": errors}

    def ingest_mapping_labels(self, run_id: str, path: str | Path) -> dict[str, Any]:
        inserted = 0
        errors: list[str] = []
        for index, label in enumerate(self._jsonl(path), start=1):
            try:
                self.record_mapping_label(run_id, label)
                inserted += 1
            except Exception as exc:
                errors.append(f"line {index}: {exc}")
        return {"inserted": inserted, "errors": errors}
