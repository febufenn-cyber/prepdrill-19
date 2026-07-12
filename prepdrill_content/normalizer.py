"""Deterministic conversion into the canonical v1 record."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ids import stable_id
from .models import utc_now


def _text_block(text: str) -> list[dict[str, Any]]:
    return [{"type": "paragraph", "text": text.strip()}]


def _normalise_options(options: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(options, list):
        return result
    for index, option in enumerate(options):
        if isinstance(option, str):
            option_id = chr(ord("A") + index)
            text = option.strip()
            blocks = _text_block(text)
        elif isinstance(option, dict):
            option_id = str(option.get("option_id") or option.get("id") or chr(ord("A") + index)).strip()
            text = str(option.get("plain_text") or option.get("text") or "").strip()
            blocks = deepcopy(option.get("blocks")) if isinstance(option.get("blocks"), list) else _text_block(text)
        else:
            option_id = chr(ord("A") + index)
            text = str(option).strip()
            blocks = _text_block(text)
        result.append({"option_id": option_id, "display_order": index, "plain_text": text, "blocks": blocks})
    return result


def normalise_phase0_record(
    raw: dict[str, Any], *, source_document_id: str, source_locator: str
) -> dict[str, Any]:
    """Normalise the Phase 0 JSONL shape without mutating the source record."""
    record = deepcopy(raw)
    original_id = str(record.get("question_id") or "").strip()
    question_id = original_id or stable_id("q", source_document_id, source_locator)
    plain_text = str(record.get("plain_text") or record.get("question_text") or "").strip()
    stem_blocks = deepcopy(record.get("stem_blocks")) if isinstance(record.get("stem_blocks"), list) else _text_block(plain_text)
    options = _normalise_options(record.get("options"))

    passage_id = record.get("passage_id")
    context_refs = list(record.get("context_refs") or [])
    if passage_id and passage_id not in context_refs:
        context_refs.append(str(passage_id))

    provenance = deepcopy(record.get("provenance") or {})
    provenance["source_document_id"] = source_document_id
    provenance["source_locator"] = source_locator

    explicit_workflow = record.get("workflow_state")
    old_state = str(record.get("publication_state") or "imported")
    if explicit_workflow in {"raw", "normalised", "review_pending", "approved", "published", "retired"}:
        workflow_state = str(explicit_workflow)
    elif old_state == "published":
        workflow_state = "approved"  # imported data must be republished through the Phase 1 gate
    elif old_state in {"human_reviewed", "official_key_verified"}:
        workflow_state = "approved"
    elif old_state in {"ambiguous", "disputed", "blocked"}:
        workflow_state = "review_pending"
    else:
        workflow_state = "normalised"

    issue_state = {
        "ambiguous": "ambiguous",
        "disputed": "disputed",
        "blocked": "blocked",
    }.get(old_state, str(record.get("issue_state") or "clear"))

    verification = deepcopy(record.get("verification") or {})
    if old_state in {"human_reviewed", "official_key_verified", "published"}:
        verification.setdefault("human_reviewed_at", utc_now())
    if old_state in {"official_key_verified", "published"} and provenance.get("answer_evidence") == "official_key":
        verification.setdefault("answer_verified_at", utc_now())

    return {
        "question_id": question_id,
        "exam": str(record.get("exam") or "ugc_net"),
        "paper": str(record.get("paper") or "paper_1"),
        "unit_id": str(record.get("unit_id") or "").strip(),
        "topic_id": record.get("topic_id"),
        "primary_concept_id": str(record.get("primary_concept_id") or "").strip(),
        "secondary_concept_ids": list(record.get("secondary_concept_ids") or []),
        "question_type": str(record.get("question_type") or "single_choice"),
        "content_language": str(record.get("content_language") or "en"),
        "source_language": str(record.get("source_language") or record.get("content_language") or "en"),
        "plain_text": plain_text,
        "stem_blocks": stem_blocks,
        "options": options,
        "correct_option_id": str(record.get("correct_option_id") or "").strip(),
        "context_refs": context_refs,
        "asset_ids": list(record.get("asset_ids") or []),
        "difficulty": str(record.get("difficulty") or "unknown"),
        "provenance": provenance,
        "workflow_state": workflow_state,
        "issue_state": issue_state,
        "validation_tier": str(record.get("validation_tier") or "review"),
        "verification": verification,
        "metadata": deepcopy(record.get("metadata") or {}),
    }
