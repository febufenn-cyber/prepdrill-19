"""Exact and explainable near-duplicate analysis."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Iterable

from .ids import exact_fingerprint, normalized_text


def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_text = normalized_text(left.get("plain_text", ""))
    right_text = normalized_text(right.get("plain_text", ""))
    stem_score = SequenceMatcher(None, left_text, right_text).ratio()
    left_options = " | ".join(normalized_text(item.get("plain_text", "")) for item in left.get("options", []))
    right_options = " | ".join(normalized_text(item.get("plain_text", "")) for item in right.get("options", []))
    option_score = SequenceMatcher(None, left_options, right_options).ratio()
    return round(stem_score * 0.75 + option_score * 0.25, 4)


def duplicate_candidates(records: Iterable[dict[str, Any]], threshold: float = 0.92) -> list[dict[str, Any]]:
    materialised = list(records)
    candidates: list[dict[str, Any]] = []
    for index, left in enumerate(materialised):
        for right in materialised[index + 1 :]:
            exact = exact_fingerprint(left) == exact_fingerprint(right)
            score = 1.0 if exact else similarity(left, right)
            if exact or score >= threshold:
                candidates.append({
                    "left_question_id": left.get("question_id"),
                    "right_question_id": right.get("question_id"),
                    "duplicate_type": "exact_content" if exact else "near_duplicate",
                    "confidence": score,
                })
    return candidates
