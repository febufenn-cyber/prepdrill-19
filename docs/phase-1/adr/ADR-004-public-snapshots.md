# ADR-004: Publish immutable snapshots into a separate boundary

## Decision

Learner-facing reads use only `content_public.published_questions` or the equivalent `PublicContentRepository`. Internal raw, core and review schemas have no learner policies.

## Consequences

Ordinary query mistakes cannot expose raw or unverified content. Corrections create and publish a new revision; the previous public snapshot is retired but preserved for history.
