# Phase 3 — Real Corpus Activation and Data Migration

Phase 3 provides the fail-closed software boundary between a delivered corpus and production learner sessions.

## Flow

```text
fresh delivery files
  → immutable manifest and checksums
  → reversible migration batch
  → relationship/count reconciliation
  → real golden/audit evidence references
  → current Phase 1.5 gate
  → named Phase 3 authorization
  → Phase 2 production activation may proceed
```

## Implemented

- deterministic manifests with mandatory roles;
- explicit fresh/fixture/legacy/generated/repaired source classification;
- count and relationship reconciliation;
- golden/audit minimum enforcement;
- rights, source, duplicate, and review-cost blockers;
- exact corpus-fingerprint pinning;
- named authorization and drift invalidation;
- append-only migration events and compensating rollback;
- service-owned Supabase schema;
- adversarial evaluator.

## Activation status

Software is complete, but real activation remains blocked until the actual UGC NET Paper 1 corpus, human reviews, rights decisions, golden set, 250-question audit, review-cost evidence, and current Phase 1.5 gate are supplied.

Run the evaluator:

```bash
python -m prepdrill_content.phase3
```
