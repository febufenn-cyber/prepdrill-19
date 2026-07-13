"""Command line operations for Prepdrill content and corpus readiness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .importer import import_file
from .readiness import GateThresholds, ReadinessRepository
from .repository import ContentRepository, PublicContentRepository


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _load_thresholds(path: Path | None) -> GateThresholds:
    if path is None:
        return GateThresholds()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("threshold file must contain a JSON object")
    return GateThresholds(**value)


def _dispatch(args: Any, repo: ContentRepository) -> int:
    if args.command == "init-db":
        _json({"status": "ok", "database": args.db})
        return 0
    if args.command == "load-taxonomy":
        count = repo.load_taxonomy(json.loads(args.path.read_text(encoding="utf-8")))
        _json({"loaded_nodes": count})
        return 0
    if args.command == "import":
        result = import_file(repo, args.path, source_document_id=args.source_document_id)
        _json(result.__dict__)
        return 1 if result.errors else 0
    if args.command == "validate":
        report = repo.validate_revision(args.revision_id, publication=args.publication)
        _json({"ok": report.ok, "findings": [item.__dict__ for item in report.findings]})
        return 0 if report.ok else 1
    if args.command == "approve":
        record = repo.update_review_state(
            args.revision_id,
            actor=args.actor,
            action="approve",
            reason=args.reason,
            workflow_state="approved",
            issue_state="clear",
        )
        _json(record)
        return 0
    if args.command == "publish":
        try:
            public_id = repo.publish(args.revision_id, actor=args.actor, reason=args.reason)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        _json({"published_question_id": public_id})
        return 0
    if args.command == "public-list":
        _json(PublicContentRepository(repo.connection).list(unit_id=args.unit_id, limit=args.limit))
        return 0
    if args.command == "readiness-report":
        _json(repo.readiness_report())
        return 0
    if args.command == "scan-duplicates":
        _json({"inserted": repo.scan_duplicate_fingerprints()})
        return 0

    readiness = ReadinessRepository(repo.connection)
    if args.command == "create-readiness-audit":
        _json(readiness.create_audit_run(
            name=args.name,
            sample_target=args.target,
            seed=args.seed,
        ))
        return 0
    if args.command == "readiness-sample":
        _json(readiness.sample_items(args.run_id))
        return 0
    if args.command == "ingest-readiness-reviews":
        result = readiness.ingest_reviews(args.run_id, args.path)
        _json(result)
        return 1 if result["errors"] else 0
    if args.command == "ingest-mapping-labels":
        result = readiness.ingest_mapping_labels(args.run_id, args.path)
        _json(result)
        return 1 if result["errors"] else 0
    if args.command == "adjudicate-duplicate":
        try:
            adjudication_id = readiness.adjudicate_duplicate(
                args.candidate_id,
                reviewer=args.reviewer,
                decision=args.decision,
                reason=args.reason,
                canonical_revision_id=args.canonical_revision_id,
            )
        except (KeyError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        _json({"adjudication_id": adjudication_id})
        return 0
    if args.command == "readiness-audit-report":
        _json(readiness.audit_report(args.run_id))
        return 0
    if args.command == "validate-golden-set":
        manifest = readiness.load_manifest(args.path)
        scope = readiness.required_scope()
        result = readiness.validate_golden_manifest(
            manifest,
            required_units=set(scope["units"]),
            required_types=set(scope["question_types"]),
        )
        _json(result)
        return 0 if result["ok"] else 1
    if args.command == "evaluate-launch-gate":
        manifest = readiness.load_manifest(args.path)
        try:
            thresholds = _load_thresholds(args.thresholds)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        report = readiness.evaluate_launch_gate(args.run_id, manifest, thresholds)
        _json(report.to_dict())
        return 0 if report.passed else 1
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prepdrill-content")
    parser.add_argument("--db", default="prepdrill-content.sqlite3", help="SQLite reference database")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")
    load_taxonomy = sub.add_parser("load-taxonomy")
    load_taxonomy.add_argument("path", type=Path)
    importer = sub.add_parser("import")
    importer.add_argument("path", type=Path)
    importer.add_argument("--source-document-id", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("revision_id")
    validate.add_argument("--publication", action="store_true")
    approve = sub.add_parser("approve")
    approve.add_argument("revision_id")
    approve.add_argument("--actor", required=True)
    approve.add_argument("--reason", required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("revision_id")
    publish.add_argument("--actor", required=True)
    publish.add_argument("--reason", required=True)
    public_list = sub.add_parser("public-list")
    public_list.add_argument("--unit-id")
    public_list.add_argument("--limit", type=int, default=100)
    sub.add_parser("readiness-report")
    sub.add_parser("scan-duplicates")

    create_audit = sub.add_parser("create-readiness-audit")
    create_audit.add_argument("--name", required=True)
    create_audit.add_argument("--target", type=int, default=250)
    create_audit.add_argument("--seed", default="phase-1.5")
    sample = sub.add_parser("readiness-sample")
    sample.add_argument("run_id")
    ingest_reviews = sub.add_parser("ingest-readiness-reviews")
    ingest_reviews.add_argument("run_id")
    ingest_reviews.add_argument("path", type=Path)
    ingest_labels = sub.add_parser("ingest-mapping-labels")
    ingest_labels.add_argument("run_id")
    ingest_labels.add_argument("path", type=Path)
    adjudicate = sub.add_parser("adjudicate-duplicate")
    adjudicate.add_argument("candidate_id")
    adjudicate.add_argument("--reviewer", required=True)
    adjudicate.add_argument("--decision", required=True, choices=("same_question", "distinct_questions", "retire_left", "retire_right"))
    adjudicate.add_argument("--canonical-revision-id")
    adjudicate.add_argument("--reason", required=True)
    audit_report = sub.add_parser("readiness-audit-report")
    audit_report.add_argument("run_id")
    validate_golden = sub.add_parser("validate-golden-set")
    validate_golden.add_argument("path", type=Path)
    launch_gate = sub.add_parser("evaluate-launch-gate")
    launch_gate.add_argument("run_id")
    launch_gate.add_argument("path", type=Path, help="Golden-set manifest")
    launch_gate.add_argument("--thresholds", type=Path)

    args = parser.parse_args(argv)
    repo = ContentRepository.open(args.db)
    try:
        return _dispatch(args, repo)
    finally:
        repo.connection.close()
