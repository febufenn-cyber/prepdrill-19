# Phase 14 Build Contract — Paper 2 English, Native Clients, and Multi-Exam Platformization

## Goal

Expand Prepdrill without duplicating or weakening the truth, readiness, runtime, identity, evaluator, and business logic established for Paper 1.

## Required software

- versioned exam/subject packs defining taxonomy, supported formats, renderer capabilities, scoring policy, mock policy, and content namespace;
- strict subject isolation for content, gates, sessions, attempts, mastery, reports, and exports;
- a separate Paper 2 English corpus fingerprint, Phase 1.5-equivalent evaluation, and named authorization;
- shared web/iOS/Android client contracts for onboarding, identity, drill state, mock state, attempts, scoring, and recovery;
- onboarding-first optional sign-in that loads the authenticated account and merges guest progress identically across clients;
- server-derived cross-client score/state fingerprints and parity checks;
- renderer capability negotiation for every supported question/block type;
- expansion scorecard using Paper 1 trust, retention, economics, operations, and regression health with explicit kill/hold/scale outcomes;
- no adjacent exam launch without a separately approved subject pack and authorization;
- Phase 14 evaluator and all inherited workflows green.

## Non-goals

- declaring Paper 2 English production-ready without its real audited corpus and authorization;
- implementing platform-specific business logic that diverges from the shared server contract;
- allowing one subject's taxonomy, attempts, mastery, or gate to leak into another;
- launching more exams because a configuration file exists;
- claiming App Store, Play Store, or production web deployment.

## Acceptance tests

Paper 2 remains locked without its own current authorization; Paper 1 authorization cannot unlock Paper 2; subject-namespaced content and learner state cannot cross; web/iOS/Android produce identical state fingerprints and scores for the same server events; onboarding-name differences still resolve to the authenticated account; unsupported renderer capabilities fail before a session starts; expansion scorecards return kill/hold/scale deterministically; unhealthy Paper 1 blocks expansion; unapproved adjacent exams remain disabled; and all inherited suites remain green.