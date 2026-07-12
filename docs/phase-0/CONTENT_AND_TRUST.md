# Content and Trust Constitution

Prepdrill cannot be more confident than its source material.

## Publication pipeline

`raw import → normalisation → automated validation → human/source review → publication → learner API`

Learner-facing services must never read raw imports directly.

## Trust rules

1. Every published question has per-question provenance.
2. AI cannot silently change a canonical answer.
3. Ambiguous or disputed items are labelled, withheld or retired.
4. Explanation confidence cannot exceed answer confidence.
5. Generated questions remain internally distinguishable forever.
6. Corrections preserve audit history.
7. Learner reports enter a review queue.
8. Correctness outranks catalogue size.
9. Missing assets block publication.
10. Prepdrill must state that it is not affiliated with UGC/NTA unless such affiliation exists.

## Provenance categories

- `official_previous_year`
- `official_sample`
- `licensed_third_party`
- `internally_authored`
- `ai_assisted_reviewed`
- `ai_generated_experimental`
- `user_submitted`

Every record stores source title, document identifier, page or question reference, ownership/licensing status and answer-key reference when available.

## Publication states

- `imported`
- `auto_validated`
- `human_reviewed`
- `official_key_verified`
- `ambiguous`
- `disputed`
- `blocked`
- `published`
- `retired`

Only records explicitly marked `published` enter normal learner drills.

## Phase 0 audit sample

Audit 250 deliberately representative questions across:

- every Paper 1 unit;
- years and shifts;
- direct MCQ, assertion/reason, matching, passages, tables, calculations, multi-statement and asset-dependent formats;
- previously known extraction failure classes.

Check structural completeness, answer validity, provenance, rendering, duplicate grouping, concept mapping and explanation suitability.

## Readiness labels

- **Gold:** official source and answer verified; structurally complete.
- **Silver:** trusted provenance and complete; answer strongly supported.
- **Review:** unresolved metadata, answer or rendering issue.
- **Blocked:** missing source, answer or required asset.
- **Retired:** unsuitable, invalid or unresolved dispute.

Phase 1 may use Gold and explicitly approved Silver items only.

## Legal/rights checklist

Before publication establish:

- right or permitted basis to reproduce each source category;
- attribution requirements;
- separation from third-party solved-paper expression;
- independently authored explanation policy;
- source-document retention policy;
- takedown and correction process.

This document is operational policy, not legal advice; unresolved rights questions require qualified review before commercial publication.
