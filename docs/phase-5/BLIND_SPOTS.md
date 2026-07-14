# Phase 5 Blind Spots

- Fluent text can contradict the official key while sounding authoritative.
- A cited source label is meaningless unless it belongs to the exact grounding bundle.
- Generic explanations can pass superficial checks while failing the learner's selected distractor.
- Cached output becomes stale when the question revision, answer evidence, prompt, or model changes.
- Provider retries can duplicate cost unless generation requests are idempotent.
- A provider outage must not block answering, scoring, review, or re-checks.
- Reviewer approval must be immutable and attributable; silently editing approved text destroys auditability.
- Model cost and latency can grow without hard ceilings and routing rules.
- AI must have no write path to canonical answers, publication state, score, or mastery.
