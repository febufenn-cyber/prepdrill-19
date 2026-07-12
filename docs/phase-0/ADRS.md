# Architecture Decision Records

These decisions are accepted for Phase 0 and must be expanded into individual ADR files when Phase 1 implementation introduces concrete migrations or APIs.

## ADR-001 — Initial exam wedge

**Decision:** UGC NET Paper 1 only. English Paper 2 is the first candidate expansion after evidence gates.

## ADR-002 — Canonical identity

**Decision:** Stable question IDs do not depend on ordering. Revisions increment versions and preserve history.

## ADR-003 — Publication pipeline

**Decision:** Raw imports cannot reach learner APIs. Only explicitly published records may be served.

## ADR-004 — Guest identity

**Decision:** Anonymous identity is independent of name. Authentication merges attempts idempotently into the Supabase user ID.

## ADR-005 — Attempts

**Decision:** Attempts are append-only events; mastery is derived and recomputable.

## ADR-006 — AI boundary

**Decision:** AI may generate explanations or review signals but cannot change answers or publish content automatically.

## ADR-007 — Provenance

**Decision:** Provenance and rights status are stored per question, not only per source document.

## ADR-008 — Product delivery

**Decision:** The first experience is mobile-first and guest-first. Native-platform expansion must not precede proof of the core loop.

## ADR-009 — Analytics privacy

**Decision:** Track stable IDs and learning interactions, avoiding full content and unnecessary personal data in external analytics.
