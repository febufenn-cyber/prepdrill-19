"""Canonical constants and small model helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

WORKFLOW_STATES = {"raw", "normalised", "review_pending", "approved", "published", "retired"}
ISSUE_STATES = {"clear", "ambiguous", "disputed", "blocked"}
VALIDATION_TIERS = {"gold", "silver", "review", "blocked", "retired"}
QUESTION_TYPES = {
    "single_choice",
    "assertion_reason",
    "match_following",
    "passage_linked",
    "table_based",
    "calculation",
    "multi_statement",
    "asset_dependent",
}
BLOCK_TYPES = {
    "paragraph",
    "labelled_statement",
    "ordered_list",
    "unordered_list",
    "table",
    "formula",
    "image",
    "match_lists",
}
PROVENANCE_CATEGORIES = {
    "official_previous_year",
    "official_sample",
    "licensed_third_party",
    "internally_authored",
    "ai_assisted_reviewed",
    "ai_generated_experimental",
    "user_submitted",
}
RIGHTS_STATUSES = {"cleared", "official_publication_reviewed", "licensed", "owned", "unknown", "blocked"}
ANSWER_EVIDENCE_TYPES = {"official_key", "licensed_key", "independent_review", "author_review", "unverified"}
PUBLISHABLE_RIGHTS = {"cleared", "official_publication_reviewed", "licensed", "owned"}
PUBLISHABLE_ANSWER_EVIDENCE = {"official_key", "licensed_key", "independent_review", "author_review"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Fields whose changes create a new learner-visible revision."""
    keys = (
        "exam",
        "paper",
        "unit_id",
        "topic_id",
        "primary_concept_id",
        "secondary_concept_ids",
        "question_type",
        "content_language",
        "source_language",
        "plain_text",
        "stem_blocks",
        "options",
        "correct_option_id",
        "context_refs",
        "asset_ids",
        "difficulty",
    )
    return {key: record.get(key) for key in keys}
