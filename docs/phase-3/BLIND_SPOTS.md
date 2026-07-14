# Phase 3 Blind Spots

- **Newly copied old data can appear fresh.** Freshness is derived from source checksums and delivery metadata, never upload time alone.
- **Aggregate counts can match while relationships are broken.** Reconciliation separately checks contexts, assets, keys, taxonomy, and source-document links.
- **A passed gate can outlive its corpus.** Authorization is bound to the exact corpus fingerprint and fails after drift.
- **Fixtures can accidentally become launch data.** Fixture, legacy, generated, and unresolved-rights counts are explicit blockers.
- **Rollback can erase evidence.** Rollback appends compensating events and never deletes import history.
- **A software evaluator can be mistaken for human evidence.** The evaluator proves enforcement only; it cannot create rights, answer, review, or learner evidence.
- **Named ownership can be ceremonial.** Owner and reason are mandatory and recorded with the exact evaluation.
