"""Readiness reporting and independent mapping agreement."""
from __future__ import annotations

import math
import statistics
from typing import Any


class ReadinessReportingMixin:
    def _latest_reviews(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT r.* FROM readiness_reviews r
            JOIN (
              SELECT run_id, revision_id, reviewer, MAX(reviewed_at) AS reviewed_at
              FROM readiness_reviews WHERE run_id=?
              GROUP BY run_id, revision_id, reviewer
            ) latest
              ON latest.run_id=r.run_id AND latest.revision_id=r.revision_id
             AND latest.reviewer=r.reviewer AND latest.reviewed_at=r.reviewed_at
            ORDER BY r.revision_id, r.reviewer
            """, (run_id,)
        )
        return [dict(row) for row in rows]

    def _latest_labels(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT l.* FROM readiness_mapping_labels l
            JOIN (
              SELECT run_id, revision_id, reviewer, MAX(recorded_at) AS recorded_at
              FROM readiness_mapping_labels WHERE run_id=?
              GROUP BY run_id, revision_id, reviewer
            ) latest
              ON latest.run_id=l.run_id AND latest.revision_id=l.revision_id
             AND latest.reviewer=l.reviewer AND latest.recorded_at=l.recorded_at
            ORDER BY l.revision_id, l.reviewer
            """, (run_id,)
        )
        return [dict(row) for row in rows]

    @staticmethod
    def _rate(values: list[int]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    @staticmethod
    def _cohen_kappa(left: list[str], right: list[str]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        observed = sum(a == b for a, b in zip(left, right)) / len(left)
        categories = sorted(set(left) | set(right))
        expected = 0.0
        for category in categories:
            expected += (left.count(category) / len(left)) * (right.count(category) / len(right))
        if math.isclose(expected, 1.0):
            return 1.0 if math.isclose(observed, 1.0) else 0.0
        return round((observed - expected) / (1.0 - expected), 4)

    def mapping_agreement(self, run_id: str) -> dict[str, Any]:
        labels = self._latest_labels(run_id)
        by_reviewer: dict[str, dict[str, str]] = {}
        for label in labels:
            by_reviewer.setdefault(str(label["reviewer"]), {})[str(label["revision_id"])] = str(label["concept_id"])
        reviewers = sorted(by_reviewer)
        pairs: list[dict[str, Any]] = []
        for index, left_name in enumerate(reviewers):
            for right_name in reviewers[index + 1:]:
                shared = sorted(set(by_reviewer[left_name]) & set(by_reviewer[right_name]))
                left = [by_reviewer[left_name][item] for item in shared]
                right = [by_reviewer[right_name][item] for item in shared]
                exact = self._rate([int(a == b) for a, b in zip(left, right)])
                pairs.append({
                    "left_reviewer": left_name,
                    "right_reviewer": right_name,
                    "shared_items": len(shared),
                    "exact_agreement": exact,
                    "cohen_kappa": self._cohen_kappa(left, right),
                })
        kappas = [pair["cohen_kappa"] for pair in pairs if pair["shared_items"]]
        shared_counts = [pair["shared_items"] for pair in pairs]
        return {
            "reviewers": reviewers,
            "pairs": pairs,
            "minimum_pair_kappa": min(kappas) if kappas else 0.0,
            "minimum_shared_items": min(shared_counts) if shared_counts else 0,
        }

    def audit_report(self, run_id: str) -> dict[str, Any]:
        run = self.connection.execute(
            "SELECT * FROM readiness_audit_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if not run:
            raise KeyError(run_id)
        sample = [dict(row) for row in self.connection.execute(
            "SELECT * FROM readiness_sample_items WHERE run_id=? ORDER BY ordinal", (run_id,)
        )]
        reviews = self._latest_reviews(run_id)
        review_by_revision: dict[str, list[dict[str, Any]]] = {}
        for review in reviews:
            review_by_revision.setdefault(str(review["revision_id"]), []).append(review)
        reviewed_items = len(review_by_revision)
        dimension_fields = (
            "rights_ok", "answer_evidence_ok", "render_ok", "mapping_ok", "provenance_ok"
        )
        dimension_rates = {
            field: self._rate([int(review[field]) for review in reviews]) for field in dimension_fields
        }
        blocking = sum(review["verdict"] != "pass" for review in reviews)
        seconds = [int(review["review_seconds"]) for review in reviews]
        sample_ids = [item["revision_id"] for item in sample]
        pending_duplicates = 0
        if sample_ids:
            placeholders = ",".join("?" for _ in sample_ids)
            pending_duplicates = int(self.connection.execute(
                f"""SELECT COUNT(*) FROM duplicate_candidates
                    WHERE status='pending' AND (
                      left_revision_id IN ({placeholders}) OR right_revision_id IN ({placeholders})
                    )""",
                tuple(sample_ids + sample_ids),
            ).fetchone()[0])
        published_active = int(self.connection.execute(
            "SELECT COUNT(*) FROM published_snapshots WHERE retired_at IS NULL"
        ).fetchone()[0])
        by_dimension: dict[str, dict[str, int]] = {}
        for field in ("unit_id", "question_type", "validation_tier"):
            counts: dict[str, int] = {}
            for item in sample:
                value = str(item[field])
                counts[value] = counts.get(value, 0) + 1
            by_dimension[field] = dict(sorted(counts.items()))
        item_by_revision = {str(item["revision_id"]): item for item in sample}
        stratum_quality: dict[str, dict[str, dict[str, Any]]] = {}
        for dimension in ("unit_id", "question_type"):
            buckets: dict[str, list[dict[str, Any]]] = {}
            for review in reviews:
                item = item_by_revision.get(str(review["revision_id"]))
                if item is not None:
                    buckets.setdefault(str(item[dimension]), []).append(review)
            stratum_quality[dimension] = {}
            for name, bucket in sorted(buckets.items()):
                pass_values = [
                    int(
                        review["verdict"] == "pass"
                        and all(int(review[field]) == 1 for field in dimension_fields)
                    )
                    for review in bucket
                ]
                stratum_quality[dimension][name] = {
                    "review_rows": len(bucket),
                    "pass_rate": self._rate(pass_values),
                }
        current_fingerprint = self.corpus_fingerprint()
        return {
            "run_id": run_id,
            "name": run["name"],
            "status": run["status"],
            "sample_target": int(run["sample_target"]),
            "population_size": int(run["population_size"]),
            "sample_size": len(sample),
            "reviewed_items": reviewed_items,
            "review_rows": len(reviews),
            "review_coverage": round(reviewed_items / len(sample), 4) if sample else 0.0,
            "dimension_pass_rates": dimension_rates,
            "blocking_reviews": blocking,
            "median_review_seconds": statistics.median(seconds) if seconds else 0.0,
            "projected_review_hours_per_1000": round((statistics.median(seconds) * 1000 / 3600), 2) if seconds else 0.0,
            "pending_duplicate_candidates": pending_duplicates,
            "published_active": published_active,
            "sample_breakdown": by_dimension,
            "stratum_quality": stratum_quality,
            "stored_corpus_fingerprint": run["corpus_fingerprint"],
            "current_corpus_fingerprint": current_fingerprint,
            "stale": current_fingerprint != run["corpus_fingerprint"],
            "mapping_agreement": self.mapping_agreement(run_id),
        }
