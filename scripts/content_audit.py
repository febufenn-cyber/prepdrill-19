#!/usr/bin/env python3
"""Audit Prepdrill canonical question records in JSON or JSONL.

Zero third-party dependencies. Validates Phase 0/1 invariants that JSON Schema
alone cannot express, including answer-option integrity and publication rules.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ALLOWED_STATES = {
    "imported", "auto_validated", "human_reviewed", "official_key_verified",
    "ambiguous", "disputed", "blocked", "published", "retired",
}
ALLOWED_TIERS = {"gold", "silver", "review", "blocked", "retired"}
ALLOWED_TYPES = {
    "single_choice", "assertion_reason", "match_following", "passage_linked",
    "table_based", "calculation", "multi_statement", "asset_dependent",
}
ALLOWED_PROVENANCE = {
    "official_previous_year", "official_sample", "licensed_third_party",
    "internally_authored", "ai_assisted_reviewed", "ai_generated_experimental",
    "user_submitted",
}


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    question_id: str
    message: str


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"line {line_no}: expected an object")
            records.append(value)
        return records

    value = json.loads(text)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise ValueError("JSON input must be an object or array of objects")


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def audit_record(record: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    qid = str(record.get("question_id") or "<missing>")

    def error(code: str, message: str) -> None:
        findings.append(Finding("error", code, qid, message))

    def warning(code: str, message: str) -> None:
        findings.append(Finding("warning", code, qid, message))

    required = [
        "question_id", "version", "exam", "paper", "unit_id",
        "primary_concept_id", "question_type", "question_text", "options",
        "correct_option_id", "provenance", "publication_state", "validation_tier",
    ]
    for key in required:
        if key not in record:
            error("missing_required", f"missing required field: {key}")

    if not nonempty_string(record.get("question_id")):
        error("invalid_question_id", "question_id must be a non-empty string")
    if not isinstance(record.get("version"), int) or record.get("version", 0) < 1:
        error("invalid_version", "version must be an integer >= 1")
    if record.get("exam") != "ugc_net" or record.get("paper") != "paper_1":
        error("scope_violation", "Phase 1 accepts only ugc_net/paper_1")
    if record.get("question_type") not in ALLOWED_TYPES:
        error("invalid_question_type", "question_type is not allowed")
    if not nonempty_string(record.get("question_text")) or len(record.get("question_text", "").strip()) < 10:
        error("short_question", "question_text must contain at least 10 characters")

    secondary = record.get("secondary_concept_ids", [])
    if not isinstance(secondary, list) or len(secondary) > 3:
        error("invalid_secondary_concepts", "secondary_concept_ids must be a list of at most 3")
    elif len(set(secondary)) != len(secondary):
        error("duplicate_secondary_concepts", "secondary concept IDs must be unique")

    options = record.get("options")
    option_ids: list[str] = []
    if not isinstance(options, list) or len(options) < 2:
        error("invalid_options", "at least two options are required")
    else:
        for index, option in enumerate(options):
            if not isinstance(option, dict):
                error("invalid_option", f"option {index} must be an object")
                continue
            option_id = option.get("option_id")
            if not nonempty_string(option_id):
                error("invalid_option_id", f"option {index} has no option_id")
            else:
                option_ids.append(option_id)
            if not nonempty_string(option.get("text")):
                error("empty_option_text", f"option {index} has empty text")
        if len(option_ids) != len(set(option_ids)):
            error("duplicate_option_ids", "option IDs must be unique")

    if record.get("correct_option_id") not in option_ids:
        error("invalid_correct_option", "correct_option_id does not reference an option")

    state = record.get("publication_state")
    tier = record.get("validation_tier")
    if state not in ALLOWED_STATES:
        error("invalid_publication_state", "publication_state is not allowed")
    if tier not in ALLOWED_TIERS:
        error("invalid_validation_tier", "validation_tier is not allowed")

    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        error("missing_provenance", "provenance must be an object")
        provenance = {}
    if provenance.get("category") not in ALLOWED_PROVENANCE:
        error("invalid_provenance_category", "provenance category is missing or invalid")
    if not nonempty_string(provenance.get("source_title")):
        error("missing_source_title", "provenance source_title is required")
    if provenance.get("rights_status") in {None, "unknown", "blocked"}:
        warning("rights_not_cleared", "rights status is not cleared")
    if provenance.get("answer_evidence") in {None, "unverified"}:
        warning("answer_unverified", "answer evidence is unverified")

    if record.get("question_type") in {"asset_dependent", "table_based"} and not record.get("asset_ids"):
        error("missing_assets", "asset-dependent/table-based question has no asset_ids")
    if record.get("question_type") == "passage_linked" and not nonempty_string(record.get("passage_id")):
        error("missing_passage", "passage-linked question has no passage_id")

    if state == "published":
        if tier not in {"gold", "silver"}:
            error("unpublishable_tier", "published question must be gold or silver")
        if provenance.get("rights_status") in {None, "unknown", "blocked"}:
            error("published_rights_unresolved", "published question requires resolved rights")
        if provenance.get("answer_evidence") in {None, "unverified"}:
            error("published_answer_unverified", "published question requires answer evidence")
        if provenance.get("category") == "ai_generated_experimental":
            error("experimental_published", "AI-generated experimental content cannot publish")

    return findings


def audit_records(records: Iterable[dict[str, Any]]) -> list[Finding]:
    materialised = list(records)
    findings: list[Finding] = []
    ids = [str(record.get("question_id")) for record in materialised if record.get("question_id")]
    for qid, count in Counter(ids).items():
        if count > 1:
            findings.append(Finding("error", "duplicate_question_id", qid, f"question_id occurs {count} times"))
    for record in materialised:
        findings.extend(audit_record(record))
    return findings


def summary(records: list[dict[str, Any]], findings: list[Finding]) -> dict[str, Any]:
    return {
        "records": len(records),
        "errors": sum(item.level == "error" for item in findings),
        "warnings": sum(item.level == "warning" for item in findings),
        "by_state": dict(Counter(str(r.get("publication_state", "<missing>")) for r in records)),
        "by_tier": dict(Counter(str(r.get("validation_tier", "<missing>")) for r in records)),
        "by_unit": dict(Counter(str(r.get("unit_id", "<missing>")) for r in records)),
        "by_type": dict(Counter(str(r.get("question_type", "<missing>")) for r in records)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="JSON or JSONL question file")
    parser.add_argument("--json", action="store_true", dest="json_output", help="emit machine-readable report")
    args = parser.parse_args(argv)

    try:
        records = load_records(args.path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"audit input error: {exc}", file=sys.stderr)
        return 2

    findings = audit_records(records)
    report = {"summary": summary(records, findings), "findings": [item.__dict__ for item in findings]}
    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for item in findings:
            print(f"{item.level.upper():7} {item.code:30} {item.question_id}: {item.message}")
        print(json.dumps(report["summary"], indent=2, sort_keys=True))

    return 1 if any(item.level == "error" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
