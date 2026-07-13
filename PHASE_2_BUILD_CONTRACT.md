# Phase 2 Build Contract — Readiness-Gated Learner Drill Runtime

## Goal

Implement the complete learner practice loop without weakening the content and corpus gates established in Phases 1 and 1.5:

```text
published snapshot → deterministic drill → immutable attempt → score
→ mastery diagnosis → grounded explanation → targeted next set → due re-check
```

Phase 2 software may be built and evaluated before the production corpus passes. **Production session creation must remain locked** until a named owner authorizes a current, passed Phase 1.5 gate evaluation.

## In scope

1. Named launch authorization tied to one current passed readiness evaluation.
2. Active-published-snapshot-only question selection.
3. Adaptive, mixed, and due-recheck session modes.
4. Deterministic selection for identical learner state and seed.
5. Immutable session item snapshots and attempt records.
6. Idempotent attempt submission and exactly-once scoring.
7. Bayesian-smoothed concept mastery and uncertainty.
8. Weakness heatmap, target concepts, and outcome diagnosis.
9. Due re-check scheduling after incorrect, skipped, or timed-out attempts.
10. Reviewed, source-grounded explanations with a fail-closed unavailable state.
11. Daily activity and streak accounting.
12. An adversarial evaluator that exercises the actual runtime implementation.
13. SQLite reference implementation, Supabase migration, OpenAPI contract, CLI, schemas, tests, and CI.

## Out of scope

- bypassing Phase 1.5 because fixtures pass;
- fabricating real learner improvement or production corpus evidence;
- generating explanations when no reviewed explanation exists;
- exposing correct answers before an attempt;
- direct learner writes to scores, mastery, re-checks, or launch authorization;
- payments, WhatsApp delivery, push notifications, or production UI styling;
- claiming psychometric calibration from the initial mastery model;
- silent destructive edits to attempts or evaluator reports.

## Runtime invariants

1. No active launch authorization means no session.
2. Authorization is valid only while the exact corpus fingerprint matches the passed gate evaluation.
3. Only active immutable published snapshots can enter a new session.
4. A session stores snapshot IDs and hashes; later corrections do not rewrite the learner's history.
5. Correct answers and reviewed explanations are removed from pre-attempt session payloads.
6. One session item accepts one final attempt. Replayed idempotency keys return the original attempt.
7. Score is derived from attempts, never accepted from a client.
8. Incorrect, skipped, and timed-out attempts reduce mastery and schedule a re-check.
9. Correct attempts raise mastery and clear pending re-checks for that snapshot.
10. Explanations are returned only when reviewed text, review timestamp, and source references exist.
11. Corpus drift immediately locks new session creation.
12. Attempts, session items, explanations, events, and evaluator reports are append-only.

## Evaluator acceptance tests

The Phase 2 evaluator must run the real runtime code and fail on any of the following:

- readiness authorization bypass;
- nondeterministic selection;
- unpublished content leakage;
- duplicate attempt creation;
- incorrect score aggregation;
- session completion errors;
- mastery moving in the wrong direction;
- weak-concept targeting below threshold;
- non-due content entering re-check mode;
- ungrounded explanation output;
- diagnosis failing to rank the weakest concept first;
- stale gate authorization remaining usable;
- fewer than the required adversarial checks.

## Completion definition

Phase 2 software is complete when:

- all inherited Phase 0, Phase 1, and Phase 1.5 checks pass;
- all Phase 2 runtime and evaluator tests pass;
- the evaluator report returns `passed: true` on its deterministic synthetic scenario;
- the production runtime remains locked without a current named authorization;
- the Supabase and OpenAPI contracts reflect the same boundaries.

Production activation remains a separate operational act requiring a real Phase 1.5 gate evaluation with `passed: true`.
