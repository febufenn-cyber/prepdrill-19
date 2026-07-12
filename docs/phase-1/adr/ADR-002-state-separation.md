# ADR-002: Separate workflow, issue and validation state

## Decision

Replace the overloaded Phase 0 publication enum with:

- `workflow_state`: raw, normalised, review_pending, approved, published, retired;
- `issue_state`: clear, ambiguous, disputed, blocked;
- `validation_tier`: gold, silver, review, blocked, retired;
- timestamped verification evidence.

## Consequences

A question can be human-reviewed yet rights-blocked, or official-key verified yet disputed, without destroying lifecycle information. This is an explicit revision of the Phase 0 draft schema.
