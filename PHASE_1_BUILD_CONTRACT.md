# Phase 1 Build Contract

This document binds Phase 1. Changes require an explicit ADR or revised contract.

## Goal

Create a trustworthy, testable content foundation for UGC NET Paper 1 and prove that canonical questions can be imported, validated, reviewed and published without learner clients touching raw data.

## User

Serious/repeat UGC NET Paper 1 aspirants. Phase 1 is infrastructure-facing, but all choices protect their trust and future guest-first experience.

## In scope

1. Canonical question and provenance schema.
2. Controlled Paper 1 unit/topic/concept identifiers.
3. Raw-to-normalised import interface.
4. Automated structural validators.
5. Duplicate and missing-asset detection hooks.
6. Publication states and review audit trail.
7. A 100-question golden regression set.
8. A 250-question representative readiness report.
9. Published-content read API or repository abstraction.
10. Tests, fixtures and CI for the above.

## Out of scope

- learner accounts and UI;
- timed drill player;
- mastery calculation;
- AI-personalised explanations;
- generated questions;
- payments, WhatsApp, streaks or leaderboards;
- exams other than UGC NET Paper 1.

## Canonical invariants

- Stable `question_id` never depends on display order.
- Content revisions are versioned.
- Exactly one primary concept; at most three secondary concepts.
- Correct answer references an existing option.
- Asset-dependent questions cannot publish without assets.
- Published questions have provenance and rights classification.
- AI cannot directly create a published record.
- Raw imports cannot be returned by learner-facing APIs.

## Required publication flow

`imported → auto_validated → human_reviewed/official_key_verified → published`

Ambiguous, disputed, blocked and retired states cannot be selected for normal drills.

## Acceptance tests

1. Valid JSONL fixtures pass the audit command with exit code 0.
2. Missing options, invalid answers, absent provenance and duplicate IDs fail with non-zero exit code.
3. Passage/asset references are checked.
4. Published-state records satisfy stricter rules than imported records.
5. Golden-set records survive import/export without semantic loss.
6. Every question can be traced to provenance and answer evidence.
7. CI runs unit tests and validates fixtures.
8. The readiness report quantifies Gold/Silver/Review/Blocked/Retired counts by unit and question type.

## Evidence required to close Phase 1

- schema and migration/DDL;
- validator report on representative corpus;
- golden-set manifest;
- test output;
- unresolved content issues list;
- architecture decision records for identity/versioning, publication pipeline and provenance.

## Phase 2 entry gate

Do not build the drill player until the selected launch corpus is renderable and the publication pipeline can prevent known broken-content classes from reaching learners.
