"""Command line operations for the Phase 1 content truth layer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .importer import import_file
from .repository import ContentRepository, PublicContentRepository


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


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

    args = parser.parse_args(argv)
    repo = ContentRepository.open(args.db)
    try:
        return _dispatch(args, repo)
    finally:
        repo.connection.close()
