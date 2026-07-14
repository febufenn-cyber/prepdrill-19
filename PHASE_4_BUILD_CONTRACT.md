# Phase 4 Build Contract — Production Application, API, and Identity Sync

## Goal

Expose the trusted learner runtime through a stable application-service boundary while preserving guest-first onboarding, correct existing-account recovery, exact server-side scoring, publication truth, and Phase 3 activation locks.

## Required software

- guest profiles and device sessions that work before sign-in;
- deterministic, idempotent guest-to-account merge into `auth.users.id`;
- correct existing-account loading even when onboarding names differ;
- collision prevention when a guest is already linked to another account;
- second-device recovery of merged progress;
- quick, topic, diagnostic, review, weakness, and re-check flow contracts;
- pre-attempt payload redaction of answers and explanations;
- server-owned score/correctness/mastery fields;
- structured renderer coverage for all supported block and question types;
- request idempotency and interrupted-session recovery;
- a Phase 4 evaluator using the same service code.

## Non-goals

- bypassing Phase 3 authorization;
- trusting client-provided correctness, score, answer key, or mastery;
- creating duplicate accounts because names differ;
- exposing internal content/review schemas;
- claiming a deployed public web application or live Supabase credentials.

## Acceptance tests

Guest attempts survive sign-in, name mismatch resolves to the authenticated account, a second device loads the same progress, merge retries are idempotent, cross-account collisions fail, unpublished/answer fields never leak, client score tampering is ignored, every flow mode is accepted deterministically, renderer fixtures cover all supported block types, interrupted sessions recover, and all inherited workflows remain green.
