"""Golden-set verification and fail-closed launch evaluation."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .ids import canonical_json, content_hash, stable_id
from .models import QUESTION_TYPES, utc_now
from .readiness_models import GateFinding, GateReport, GateThresholds


class ReadinessGateMixin:
    def validate_golden_manifest(
        self,
        manifest: dict[str, Any],
        *,
        required_units: set[str] | None = None,
        required_types: set[str] | None = None,
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        entries = manifest.get("entries")
        if not isinstance(entries, list):
            entries = []
            findings.append({"level": "error", "code": "entries_missing", "message": "entries must be a list"})
        target_size = int(manifest.get("target_size", 0) or 0)
        if int(manifest.get("current_size", len(entries)) or 0) != len(entries):
            findings.append({"level": "error", "code": "current_size_mismatch", "message": "current_size must equal entries length"})
        if len(entries) < target_size:
            findings.append({"level": "error", "code": "golden_set_incomplete", "message": "entries are below target_size"})

        revision_rows = {
            str(row["revision_id"]): row for row in self.connection.execute(
                "SELECT revision_id, question_id, semantic_hash, content_json FROM question_revisions"
            )
        }
        seen_revisions: set[str] = set()
        seen_questions: set[str] = set()
        units: set[str] = set()
        types: set[str] = set()
        required_fields = {
            "revision_id", "question_id", "unit_id", "question_type", "source_checksum",
            "expected_canonical_hash", "expected_validator_codes",
        }
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                findings.append({"level": "error", "code": "invalid_entry", "message": f"entry {index} must be an object"})
                continue
            missing = sorted(required_fields - set(entry))
            if missing:
                findings.append({"level": "error", "code": "missing_entry_fields", "message": f"entry {index}: {', '.join(missing)}"})
                continue
            revision_id = str(entry["revision_id"])
            question_id = str(entry["question_id"])
            if revision_id in seen_revisions:
                findings.append({"level": "error", "code": "duplicate_revision", "message": revision_id})
            if question_id in seen_questions:
                findings.append({"level": "error", "code": "duplicate_question", "message": question_id})
            seen_revisions.add(revision_id)
            seen_questions.add(question_id)
            units.add(str(entry["unit_id"]))
            types.add(str(entry["question_type"]))
            row = revision_rows.get(revision_id)
            if row is None:
                findings.append({"level": "error", "code": "unknown_revision", "message": revision_id})
                continue
            payload = json.loads(row["content_json"])
            comparisons = {
                "question_id": str(row["question_id"]),
                "unit_id": str(payload.get("unit_id")),
                "question_type": str(payload.get("question_type")),
                "expected_canonical_hash": str(row["semantic_hash"]),
            }
            for field, actual in comparisons.items():
                if str(entry[field]) != actual:
                    findings.append({"level": "error", "code": f"{field}_mismatch", "message": revision_id})
            if not isinstance(entry["expected_validator_codes"], list):
                findings.append({"level": "error", "code": "invalid_expected_validator_codes", "message": revision_id})
            source_checksum = str(entry["source_checksum"]).strip()
            if not source_checksum:
                findings.append({"level": "error", "code": "missing_source_checksum", "message": revision_id})
            else:
                known_checksums = {str(item[0]) for item in self.connection.execute(
                    """SELECT ib.source_checksum
                       FROM source_links sl
                       JOIN import_batches ib ON ib.source_document_id=sl.source_document_id
                       WHERE sl.revision_id=?""", (revision_id,)
                )}
                if not known_checksums:
                    findings.append({"level": "error", "code": "missing_source_evidence", "message": revision_id})
                elif source_checksum not in known_checksums:
                    findings.append({"level": "error", "code": "source_checksum_mismatch", "message": revision_id})

            validation_mode = str(entry.get("validation_mode") or "normal")
            if validation_mode not in {"normal", "publication"}:
                findings.append({"level": "error", "code": "invalid_validation_mode", "message": revision_id})
            else:
                mode = 1 if validation_mode == "publication" else 0
                validation_run = self.connection.execute(
                    """SELECT validation_run_id FROM validation_runs
                       WHERE revision_id=? AND publication_mode=?
                       ORDER BY created_at DESC LIMIT 1""",
                    (revision_id, mode),
                ).fetchone()
                if not validation_run:
                    findings.append({"level": "error", "code": "missing_validation_run", "message": revision_id})
                elif isinstance(entry["expected_validator_codes"], list):
                    actual_codes = sorted(str(item[0]) for item in self.connection.execute(
                        "SELECT code FROM validation_findings WHERE validation_run_id=? ORDER BY code",
                        (validation_run[0],),
                    ))
                    expected_codes = sorted(str(code) for code in entry["expected_validator_codes"])
                    if actual_codes != expected_codes:
                        findings.append({
                            "level": "error", "code": "validator_codes_mismatch",
                            "message": f"{revision_id}: expected {expected_codes}, actual {actual_codes}",
                        })

        if required_units:
            missing_units = sorted(required_units - units)
            if missing_units:
                findings.append({"level": "error", "code": "missing_units", "message": ", ".join(missing_units)})
        if required_types:
            missing_types = sorted(required_types - types)
            if missing_types:
                findings.append({"level": "error", "code": "missing_question_types", "message": ", ".join(missing_types)})
        return {
            "ok": not any(item["level"] == "error" for item in findings),
            "target_size": target_size,
            "entry_count": len(entries),
            "units": sorted(units),
            "question_types": sorted(types),
            "fingerprint": content_hash(manifest),
            "findings": findings,
        }

    def _required_units(self) -> set[str]:
        return {str(row[0]) for row in self.connection.execute(
            "SELECT node_id FROM taxonomy_nodes WHERE node_type='unit' AND active=1"
        )}

    def _required_types(self) -> set[str]:
        return set(QUESTION_TYPES)

    def required_scope(self) -> dict[str, list[str]]:
        return {
            "units": sorted(self._required_units()),
            "question_types": sorted(self._required_types()),
        }

    def evaluate_launch_gate(
        self,
        run_id: str,
        manifest: dict[str, Any],
        thresholds: GateThresholds | None = None,
    ) -> GateReport:
        limits = thresholds or GateThresholds()
        audit = self.audit_report(run_id)
        golden = self.validate_golden_manifest(
            manifest,
            required_units=self._required_units(),
            required_types=self._required_types(),
        )
        findings: list[GateFinding] = []

        def require(code: str, ok: bool, message: str, observed: Any, required: Any) -> None:
            if not ok:
                findings.append(GateFinding("error", code, message, observed, required))

        require("audit_stale", not audit["stale"], "audit corpus fingerprint is stale", audit["current_corpus_fingerprint"], audit["stored_corpus_fingerprint"])
        require("audit_sample_short", audit["sample_size"] >= limits.audit_target, "representative audit is undersized", audit["sample_size"], limits.audit_target)
        require("audit_incomplete", audit["reviewed_items"] == audit["sample_size"], "every sampled item requires review", audit["reviewed_items"], audit["sample_size"])
        for field, rate in audit["dimension_pass_rates"].items():
            require(f"{field}_rate_low", rate >= limits.dimension_pass_rate_min, f"{field} pass rate is below threshold", rate, limits.dimension_pass_rate_min)
        require("blocking_reviews", audit["blocking_reviews"] <= limits.max_blocking_reviews, "blocking review verdicts remain", audit["blocking_reviews"], limits.max_blocking_reviews)
        for dimension, buckets in audit["stratum_quality"].items():
            for name, metrics in buckets.items():
                require(
                    f"{dimension}_stratum_low",
                    metrics["pass_rate"] >= limits.stratum_pass_rate_min,
                    f"{dimension} stratum {name} is below the pass-rate floor",
                    metrics["pass_rate"], limits.stratum_pass_rate_min,
                )
        require("review_time_missing", audit["median_review_seconds"] > 0, "review cost has not been measured", audit["median_review_seconds"], "> 0")
        require("duplicates_pending", audit["pending_duplicate_candidates"] <= limits.max_pending_duplicates, "duplicate candidates remain unresolved", audit["pending_duplicate_candidates"], limits.max_pending_duplicates)
        require("launch_subset_small", audit["published_active"] >= limits.launch_min_published, "launch subset is too small", audit["published_active"], limits.launch_min_published)
        require("golden_invalid", golden["ok"], "golden-set manifest is invalid", golden["findings"], "no errors")
        require("golden_short", golden["entry_count"] >= limits.golden_target, "golden set is undersized", golden["entry_count"], limits.golden_target)
        require("unit_coverage", len(golden["units"]) >= limits.required_unit_count, "golden set lacks Paper 1 unit coverage", len(golden["units"]), limits.required_unit_count)
        agreement = audit["mapping_agreement"]
        require("mapping_overlap_short", agreement["minimum_shared_items"] >= limits.mapping_min_items, "mapping agreement sample is too small", agreement["minimum_shared_items"], limits.mapping_min_items)
        require("mapping_kappa_low", agreement["minimum_pair_kappa"] >= limits.mapping_kappa_min, "mapping agreement is below threshold", agreement["minimum_pair_kappa"], limits.mapping_kappa_min)

        report = GateReport(
            run_id=run_id,
            corpus_fingerprint=audit["current_corpus_fingerprint"],
            golden_fingerprint=golden["fingerprint"],
            passed=not findings,
            metrics={"audit": audit, "golden": golden, "thresholds": asdict(limits)},
            findings=tuple(findings),
        )
        evaluation_id = stable_id(
            "gate", run_id, report.corpus_fingerprint, report.golden_fingerprint,
            canonical_json(asdict(limits)),
        )
        self.connection.execute(
            "INSERT OR REPLACE INTO readiness_gate_evaluations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                evaluation_id, run_id, report.corpus_fingerprint, report.golden_fingerprint,
                int(report.passed), canonical_json(report.to_dict()), utc_now(),
            ),
        )
        self.connection.commit()
        return report

    @staticmethod
    def load_manifest(path: str | Path) -> dict[str, Any]:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("golden manifest must be a JSON object")
        return value
