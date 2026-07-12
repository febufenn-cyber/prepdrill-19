# ADR-001: Separate source, canonical, revision and publication identities

## Decision

Use four identities:

- raw/source occurrence identity;
- stable canonical `question_id`;
- immutable `revision_id` for a semantic version;
- immutable `published_question_id` for the public snapshot.

Learner attempts will later reference the exact published revision shown.

## Consequences

Corrections do not rewrite history. Repeated sources can link to one canonical item. Published content can be retired without deleting source or revision evidence.
