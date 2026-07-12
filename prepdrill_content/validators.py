"""Layered validation for canonical questions and publication decisions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .ids import normalized_text, valid_stable_id
from .models import (
    ANSWER_EVIDENCE_TYPES,
    BLOCK_TYPES,
    ISSUE_STATES,
    PROVENANCE_CATEGORIES,
    PUBLISHABLE_ANSWER_EVIDENCE,
    PUBLISHABLE_RIGHTS,
    QUESTION_TYPES,
    RIGHTS_STATUSES,
    VALIDATION_TIERS,
    WORKFLOW_STATES,
)


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    path: str = ""


@dataclass(frozen=True)
class ValidationReport:
    findings: tuple[Finding, ...]

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.level == "error")

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.findings if item.level == "warning")

    @property
    def ok(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {item.code for item in self.findings}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_block(blocks: Iterable[Any], block_type: str) -> bool:
    return any(isinstance(block, dict) and block.get("type") == block_type for block in blocks)


def validate_question(
    record: dict[str, Any], *, publication: bool = False, known_assets: set[str] | None = None,
    known_contexts: set[str] | None = None,
) -> ValidationReport:
    findings: list[Finding] = []

    def error(code: str, message: str, path: str = "") -> None:
        findings.append(Finding("error", code, message, path))

    def warning(code: str, message: str, path: str = "") -> None:
        findings.append(Finding("warning", code, message, path))

    required = {
        "question_id", "exam", "paper", "unit_id", "primary_concept_id", "question_type",
        "content_language", "plain_text", "stem_blocks", "options", "correct_option_id",
        "provenance", "workflow_state", "issue_state", "validation_tier", "verification",
    }
    for key in sorted(required - set(record)):
        error("missing_required", f"missing required field: {key}", key)

    if not valid_stable_id(record.get("question_id")):
        error("invalid_question_id", "question_id must be a stable lowercase identifier", "question_id")
    if record.get("exam") != "ugc_net" or record.get("paper") != "paper_1":
        error("scope_violation", "Phase 1 accepts only ugc_net/paper_1")
    if not _nonempty(record.get("unit_id")):
        error("missing_unit", "unit_id is required", "unit_id")
    if not _nonempty(record.get("primary_concept_id")):
        error("missing_primary_concept", "primary_concept_id is required", "primary_concept_id")

    secondary = record.get("secondary_concept_ids", [])
    if not isinstance(secondary, list) or len(secondary) > 3:
        error("invalid_secondary_concepts", "secondary_concept_ids must contain at most three IDs")
    elif len(set(secondary)) != len(secondary):
        error("duplicate_secondary_concepts", "secondary concept IDs must be unique")
    elif record.get("primary_concept_id") in secondary:
        error("primary_repeated_as_secondary", "primary concept cannot also be secondary")

    qtype = record.get("question_type")
    if qtype not in QUESTION_TYPES:
        error("invalid_question_type", "unsupported question_type", "question_type")
    plain_text = record.get("plain_text")
    if not _nonempty(plain_text) or len(plain_text.strip()) < 10:
        error("short_question", "plain_text must contain at least ten characters", "plain_text")

    stem_blocks = record.get("stem_blocks")
    if not isinstance(stem_blocks, list) or not stem_blocks:
        error("missing_stem_blocks", "at least one stem block is required", "stem_blocks")
    else:
        for index, block in enumerate(stem_blocks):
            if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
                error("invalid_stem_block", "stem block type is unsupported", f"stem_blocks[{index}]")

    options = record.get("options")
    option_ids: list[str] = []
    option_texts: list[str] = []
    if not isinstance(options, list) or len(options) < 2:
        error("invalid_options", "at least two options are required", "options")
    else:
        for index, option in enumerate(options):
            path = f"options[{index}]"
            if not isinstance(option, dict):
                error("invalid_option", "option must be an object", path)
                continue
            option_id = option.get("option_id")
            text = option.get("plain_text")
            if not _nonempty(option_id):
                error("invalid_option_id", "option_id is required", path)
            else:
                option_ids.append(option_id)
            if not _nonempty(text):
                error("empty_option_text", "option plain_text is required", path)
            else:
                option_texts.append(normalized_text(text))
            if not isinstance(option.get("blocks"), list) or not option.get("blocks"):
                error("missing_option_blocks", "option blocks are required", path)
        if len(option_ids) != len(set(option_ids)):
            error("duplicate_option_ids", "option IDs must be unique", "options")
        if len(option_texts) != len(set(option_texts)):
            error("duplicate_option_text", "normalised option texts must be unique", "options")

    if record.get("correct_option_id") not in option_ids:
        error("invalid_correct_option", "correct_option_id must reference an existing option", "correct_option_id")

    if record.get("workflow_state") not in WORKFLOW_STATES:
        error("invalid_workflow_state", "workflow_state is invalid", "workflow_state")
    if record.get("issue_state") not in ISSUE_STATES:
        error("invalid_issue_state", "issue_state is invalid", "issue_state")
    if record.get("validation_tier") not in VALIDATION_TIERS:
        error("invalid_validation_tier", "validation_tier is invalid", "validation_tier")

    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        error("missing_provenance", "provenance object is required", "provenance")
        provenance = {}
    if provenance.get("category") not in PROVENANCE_CATEGORIES:
        error("invalid_provenance_category", "provenance category is invalid", "provenance.category")
    if not _nonempty(provenance.get("source_title")):
        error("missing_source_title", "source_title is required", "provenance.source_title")
    if not _nonempty(provenance.get("source_document_id")):
        error("missing_source_document", "source_document_id is required", "provenance.source_document_id")
    if not _nonempty(provenance.get("source_locator")):
        error("missing_source_locator", "source_locator is required", "provenance.source_locator")
    if provenance.get("rights_status") not in RIGHTS_STATUSES:
        error("invalid_rights_status", "rights_status is invalid", "provenance.rights_status")
    if provenance.get("answer_evidence") not in ANSWER_EVIDENCE_TYPES:
        error("invalid_answer_evidence", "answer_evidence is invalid", "provenance.answer_evidence")

    context_refs = record.get("context_refs", [])
    asset_ids = record.get("asset_ids", [])
    if not isinstance(context_refs, list):
        error("invalid_context_refs", "context_refs must be a list", "context_refs")
        context_refs = []
    if not isinstance(asset_ids, list):
        error("invalid_asset_ids", "asset_ids must be a list", "asset_ids")
        asset_ids = []

    if qtype == "passage_linked" and not context_refs:
        error("missing_context", "passage-linked question requires a context reference")
    if qtype == "table_based" and not (_contains_block(stem_blocks or [], "table") or asset_ids or context_refs):
        error("missing_table", "table-based question requires a table block, asset or shared context")
    if qtype == "asset_dependent" and not asset_ids:
        error("missing_assets", "asset-dependent question requires asset IDs")
    if known_contexts is not None:
        for context_id in context_refs:
            if context_id not in known_contexts:
                error("unresolved_context", f"context does not exist: {context_id}")
    if known_assets is not None:
        for asset_id in asset_ids:
            if asset_id not in known_assets:
                error("unresolved_asset", f"asset does not exist: {asset_id}")

    lowered = normalized_text(str(plain_text or ""))
    if re.search(r"\b(refer|based)\b.*\btable\b", lowered) and not (_contains_block(stem_blocks or [], "table") or asset_ids or context_refs):
        warning("table_reference_without_table", "question text refers to a table but none is linked")
    if "given below given below" in lowered:
        warning("repeated_phrase", "question contains repeated extraction phrase")
    if lowered.endswith(("and", "or", ":", ";")):
        warning("possibly_truncated", "question may end abruptly")

    if publication:
        if record.get("workflow_state") not in {"approved", "published"}:
            error("not_approved", "only approved content can be published")
        if record.get("issue_state") != "clear":
            error("blocking_issue", "published content must have issue_state=clear")
        if record.get("validation_tier") not in {"gold", "silver"}:
            error("unpublishable_tier", "published content must be gold or silver")
        if provenance.get("rights_status") not in PUBLISHABLE_RIGHTS:
            error("published_rights_unresolved", "publication requires resolved rights")
        if provenance.get("answer_evidence") not in PUBLISHABLE_ANSWER_EVIDENCE:
            error("published_answer_unverified", "publication requires verified answer evidence")
        if provenance.get("category") == "ai_generated_experimental":
            error("experimental_published", "experimental AI content cannot publish")
        verification = record.get("verification") if isinstance(record.get("verification"), dict) else {}
        for key in ("structural_validated_at", "source_verified_at", "answer_verified_at", "human_reviewed_at", "rights_cleared_at"):
            if not _nonempty(verification.get(key)):
                error("missing_verification", f"publication requires {key}", f"verification.{key}")
        if asset_ids and not _nonempty(verification.get("assets_verified_at")):
            error("missing_asset_verification", "asset-bearing content requires assets_verified_at")

    return ValidationReport(tuple(findings))
