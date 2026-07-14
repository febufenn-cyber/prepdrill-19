# Phase 3 Build Contract — Real Corpus Activation and Data Migration

## Goal

Convert a fresh UGC NET Paper 1 corpus delivery into an auditable, reversible launch candidate without allowing fixtures, legacy samples, generated questions, unresolved rights, broken assets, or stale evaluations into production.

## Required software

- immutable source-delivery manifests with checksums and declared roles;
- deterministic reconciliation of records, contexts, assets, keys, taxonomy, and source documents;
- explicit classification of fixture, legacy, generated, repaired, and launch-eligible inputs;
- reversible migration batches and append-only migration events;
- launch evaluation pinned to an exact corpus fingerprint;
- named-owner authorization that automatically becomes invalid after corpus drift;
- a Phase 3 evaluator exercising positive and adversarial activation paths;
- Supabase schema with service-owned writes and no learner access.

## Required real evidence

Production activation additionally requires a real 100-question golden set, real 250-question stratified audit, resolved rights/provenance/answer/rendering/mapping evidence, duplicate adjudication, measured review cost, and a current passed Phase 1.5 gate.

## Non-goals

- fabricating corpus evidence or rights decisions;
- publishing or activating fixture data;
- rewriting Phase 1 or 1.5 history;
- bypassing the Phase 2 launch authorization boundary;
- destructive replacement of previous import batches.

## Acceptance tests

1. Missing manifest roles fail.
2. Count mismatches and orphaned contexts/assets fail.
3. Fixture, legacy, generated, or unresolved-rights launch items fail.
4. Golden-set size below 100 or audit size below 250 fails.
5. A failed or stale Phase 1.5 gate fails.
6. A passed evaluation requires a named owner to authorize.
7. Corpus drift invalidates authorization.
8. Rollback is append-only and preserves evidence.
9. Identical manifests produce identical fingerprints.
10. All inherited workflows remain green.
