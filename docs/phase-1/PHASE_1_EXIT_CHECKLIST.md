# Phase 1 Exit Checklist

## Software invariants

- [x] Raw imports are immutable and checksummed.
- [x] Re-importing identical source data is idempotent.
- [x] Canonical questions and revisions have separate identities.
- [x] Semantic corrections create a new revision.
- [x] Workflow stage, issue state and validation tier are separate.
- [x] Answer claims and source links are preserved.
- [x] Missing contexts/assets block relevant question types.
- [x] Publication validation is stricter than import validation.
- [x] Experimental AI content cannot publish.
- [x] Published snapshots are immutable and supersede older snapshots.
- [x] Public reads cannot query raw/review content through the public repository.
- [x] Validation findings and review decisions are auditable.
- [x] CI runs the Phase 1 tests and smoke workflow.

## Corpus evidence

- [ ] 100-question golden set populated from real source material.
- [ ] Golden set has reviewed expected outputs and validator findings.
- [ ] 250-question representative audit completed.
- [ ] Gold/Silver/Review/Blocked/Retired report completed by unit and type.
- [ ] Rights classification completed for the launch subset.
- [ ] Answer evidence completed for the launch subset.
- [ ] Concept-mapping agreement measured.
- [ ] Duplicate candidates adjudicated.
- [ ] Human review cost per 100/1,000 questions measured.
- [ ] Unresolved content-issues list reviewed and accepted.

Phase 2 must not begin until the selected launch corpus is renderable and the publication gate has demonstrated that known broken-content classes cannot reach public reads.
