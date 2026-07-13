# Phase 1.5 Build Contract — Corpus Readiness and Launch Gate

This phase exists because Phase 1 software is complete while the evidence needed to trust a launch corpus is not. It must convert subjective confidence into pinned, reproducible, fail-closed evidence.

## Goal

Prove that a real UGC NET Paper 1 launch corpus is representative, rights-cleared, answer-verified, renderable, consistently mapped, duplicate-adjudicated, and affordable to review before learner-facing Phase 2 work begins.

## Move-order decision

Do **not** build the drill player yet. The next irreversible risk is not UI quality; it is scaling a corpus whose errors, rights, mappings, and review costs are still unknown.

## In scope

1. Immutable audit runs pinned to exact revision hashes.
2. Deterministic stratified selection across unit, question type, and validation tier.
3. A 250-question representative audit workflow.
4. A 100-question golden-set validator tied to real source checksums and validator outputs.
5. Append-only review evidence for rights, answer evidence, rendering, mapping, provenance, verdict, notes, and review time.
6. Independent mapping labels and Cohen's kappa measurement.
7. Audited duplicate adjudication without destructive automatic merging.
8. Per-unit and per-question-type quality floors, not only aggregate averages.
9. Corpus-drift detection that invalidates stale audit results.
10. An immutable, configurable launch-gate evaluation.
11. SQLite reference implementation, Supabase migration, CLI, tests, schemas, and CI.

## Out of scope

- learner UI, drill sessions, attempts, streaks, payments, or AI explanations;
- inventing or committing copyrighted source material;
- fabricating reviewer identities, review outcomes, rights decisions, or timings;
- automatically merging or deleting duplicate questions;
- weakening thresholds merely to make the gate pass;
- treating fixture evidence as production evidence.

## Default launch thresholds

- representative audit: at least 250 pinned latest revisions;
- reviewed coverage: 100% of sampled revisions;
- golden set: at least 100 unique questions;
- Paper 1 unit coverage: all 10 units;
- question-type coverage: every supported canonical question type;
- rights, answer evidence, rendering, mapping, and provenance pass rates: 100%;
- per-unit and per-type quality floor: 100%;
- unresolved blocking review verdicts: 0;
- pending duplicate candidates touching the audit sample: 0;
- active published launch subset: at least 100 questions;
- independent concept-mapping overlap: at least 50 items;
- minimum pairwise Cohen's kappa: 0.80;
- review-time measurement: present and non-zero;
- audit corpus fingerprint: current, not stale.

Changing these defaults requires an explicit threshold file whose complete contents are stored in the gate report. Product decisions should additionally record an ADR.

## Acceptance tests

1. Identical corpus, seed, target, and audit name produce the same run and sample.
2. Sampling covers the available strata instead of selecting only easy/direct questions.
3. Reviews outside the pinned sample are rejected.
4. Boolean review fields reject truthy strings such as `"false"`.
5. Golden entries are checked against revision hash, source checksum, and validator findings.
6. A corpus revision after audit creation makes the run stale.
7. Mapping agreement is calculated only from shared independently labelled items.
8. Duplicate adjudication is append-only and clears only the selected candidate.
9. A gate with missing evidence fails closed and names every blocker.
10. A fully evidenced synthetic corpus can pass the gate.

## Phase 2 entry gate

Phase 2 may begin only after a gate evaluation on the real launch corpus returns `passed: true`, its corpus fingerprint still matches the latest revisions, and the evidence is reviewed by a named owner.
