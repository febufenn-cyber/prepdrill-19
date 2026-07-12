"""Adapter-driven, idempotent raw-to-canonical import pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Protocol

from .ids import content_hash
from .normalizer import normalise_phase0_record
from .repository import ContentRepository


class SourceAdapter(Protocol):
    name: str
    version: str

    def records(self, source: Path) -> Iterator[tuple[str, dict[str, Any]]]: ...


class Phase0JsonlAdapter:
    name = "phase0-jsonl"
    version = "1"

    def records(self, source: Path) -> Iterator[tuple[str, dict[str, Any]]]:
        text = source.read_text(encoding="utf-8")
        if source.suffix.lower() == ".jsonl":
            for line_no, line in enumerate(text.splitlines(), start=1):
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError(f"line {line_no}: expected JSON object")
                    locator = str(value.get("source_question_number") or f"line:{line_no}")
                    yield locator, value
            return
        value = json.loads(text)
        values = value if isinstance(value, list) else [value]
        for index, item in enumerate(values, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"item {index}: expected JSON object")
            locator = str(item.get("source_question_number") or f"item:{index}")
            yield locator, item


@dataclass(frozen=True)
class ImportResult:
    import_batch_id: str
    batch_created: bool
    raw_created: int
    raw_reused: int
    revisions_created: int
    revisions_reused: int
    validation_errors: int
    validation_warnings: int
    errors: tuple[str, ...]


def import_records(
    repository: ContentRepository,
    *,
    source_document_id: str,
    source_checksum: str,
    records: Iterable[tuple[str, dict[str, Any]]],
    adapter_name: str = "phase0-jsonl",
    adapter_version: str = "1",
) -> ImportResult:
    batch_id, batch_created = repository.create_or_get_batch(
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        source_document_id=source_document_id,
        source_checksum=source_checksum,
    )
    raw_created = raw_reused = revisions_created = revisions_reused = 0
    validation_errors = validation_warnings = 0
    errors: list[str] = []
    for locator, raw in records:
        try:
            _, created_raw = repository.store_raw(batch_id=batch_id, source_locator=locator, raw=raw)
            raw_created += int(created_raw)
            raw_reused += int(not created_raw)
            canonical = normalise_phase0_record(raw, source_document_id=source_document_id, source_locator=locator)
            revision_id, _, created_revision = repository.upsert_revision(canonical)
            revisions_created += int(created_revision)
            revisions_reused += int(not created_revision)
            report = repository.validate_revision(revision_id, publication=False)
            validation_errors += len(report.errors)
            validation_warnings += len(report.warnings)
        except Exception as exc:  # one bad item must not destroy a resumable batch
            errors.append(f"{locator}: {exc}")
    repository.complete_batch(batch_id)
    return ImportResult(
        import_batch_id=batch_id,
        batch_created=batch_created,
        raw_created=raw_created,
        raw_reused=raw_reused,
        revisions_created=revisions_created,
        revisions_reused=revisions_reused,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
        errors=tuple(errors),
    )


def import_file(repository: ContentRepository, source: Path, *, source_document_id: str, adapter: SourceAdapter | None = None) -> ImportResult:
    selected = adapter or Phase0JsonlAdapter()
    checksum = content_hash(source.read_text(encoding="utf-8"))
    return import_records(
        repository,
        source_document_id=source_document_id,
        source_checksum=checksum,
        records=selected.records(source),
        adapter_name=selected.name,
        adapter_version=selected.version,
    )
