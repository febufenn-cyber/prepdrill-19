# Architecture and Security V0

## System boundary

```text
client/PWA
  → Cloudflare Worker + Hono API
    → Supabase Postgres/Auth/RLS
    → published content + append-only attempts
    → mastery/recommendation jobs
    → provider-abstracted explanation service
```

Raw corpora and internal review tables are outside the public learner API boundary.

## Source of truth

Supabase Postgres owns:

- published questions and provenance;
- user identity linkage;
- attempt events;
- derived learner-concept state;
- recommendations;
- content reports and review history;
- future entitlements.

Object storage may hold source PDFs/assets, but database records preserve stable references and publication status.

## Identity contract

- Learners may complete the first drill as guests.
- Guest attempts use an anonymous, non-name identity.
- On authentication, guest attempts merge into the Supabase authenticated user ID.
- Names, email display values or onboarding answers never determine account identity.
- Merge operations are idempotent and auditable.
- Reinstall/sign-in must restore the authenticated profile and progress.

## Data rules

- Attempts are append-only; corrections create compensating/audit events.
- Derived mastery can be recomputed from event history.
- Canonical answer changes are versioned.
- Question publication and content editing are separate permissions.
- Public APIs return only published content.

## AI boundary

- Practice works when the AI provider is unavailable.
- Providers sit behind an internal interface.
- Calls are logged, rate-limited and cached.
- Prompts include verified answer/provenance and constrained output schemas.
- AI output cannot mutate canonical answers or publish content directly.
- Conflicts enter review queues.

## RLS intent

Learners may access:

- their own profile, attempts and recommendations;
- published public question content;
- explanation content they are entitled to view.

Learners may not access:

- other users' events;
- raw imports;
- unpublished or disputed content;
- internal licensing notes;
- review queues or model diagnostics.

## ADRs to create during implementation

1. Initial exam wedge
2. Canonical question identity/versioning
3. Publication pipeline
4. Guest-to-auth merge
5. Attempt event model
6. Mastery computation ownership
7. AI explanation boundary
8. Provenance and rights metadata
9. Delivery platform
10. Analytics/privacy
