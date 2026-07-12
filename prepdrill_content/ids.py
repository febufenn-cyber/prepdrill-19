"""Stable identity and fingerprint helpers."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{5,127}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_hash(value: Any) -> str:
    return sha256_text(canonical_json(value))


def stable_id(prefix: str, *parts: str, length: int = 24) -> str:
    material = "\x1f".join(str(part).strip() for part in parts)
    return f"{prefix}:{sha256_text(material)[:length]}"


def valid_stable_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID_RE.fullmatch(value))


def normalized_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\w\s%+\-./]", "", text)
    return text


def exact_fingerprint(record: dict[str, Any]) -> str:
    payload = {
        "stem": normalized_text(record.get("plain_text", "")),
        "options": [normalized_text(option.get("plain_text", "")) for option in record.get("options", [])],
    }
    return content_hash(payload)


def near_fingerprint(record: dict[str, Any]) -> str:
    tokens = normalized_text(record.get("plain_text", "")).split()
    option_tokens: list[str] = []
    for option in record.get("options", []):
        option_tokens.extend(normalized_text(option.get("plain_text", "")).split())
    token_bag = sorted(set(tokens + option_tokens))
    return sha256_text(" ".join(token_bag))
