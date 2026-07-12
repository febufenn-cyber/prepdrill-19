# Phase 0 — Position Before Movement

Phase 0 reduces strategic uncertainty before production engineering. It does not pretend that plans equal evidence.

## Binding hypothesis

> Prepdrill helps serious UGC NET Paper 1 repeat aspirants convert mistakes into focused daily practice using verified questions and transparent recommendations.

## Deliverables

| Area | Document | Completion evidence |
|---|---|---|
| Product | [PRODUCT_CHARTER.md](PRODUCT_CHARTER.md) | First user, job, promise, non-goals locked |
| Research | [RESEARCH_PLAN.md](RESEARCH_PLAN.md) | Interviews and prototype tests recorded |
| Content | [CONTENT_AND_TRUST.md](CONTENT_AND_TRUST.md) | Audit sample, provenance and publication states defined |
| Learning | [LEARNING_SYSTEM_V0.md](LEARNING_SYSTEM_V0.md) | Mastery and recommendation semantics defined |
| Architecture | [ARCHITECTURE_AND_SECURITY_V0.md](ARCHITECTURE_AND_SECURITY_V0.md) | Boundaries and identity rules locked |
| Analytics/GTM | [ANALYTICS_AND_GTM.md](ANALYTICS_AND_GTM.md) | Events, metrics and smoke tests defined |
| Governance | [RISK_AND_EXIT_GATES.md](RISK_AND_EXIT_GATES.md) | Critical risks and advance rule defined |
| Handoff | [`PHASE_1_BUILD_CONTRACT.md`](../../PHASE_1_BUILD_CONTRACT.md) | Phase 1 scope and acceptance tests locked |

## Executable assets

- `schemas/question.schema.json` validates canonical question records.
- `scripts/content_audit.py` audits JSON or JSONL without third-party dependencies.
- `tests/test_content_audit.py` protects core validator behaviour.
- `data/golden-set/README.md` defines the permanent regression set.
- `prototypes/README.md` defines the six-screen usability prototype.

## Phase 0 evidence board

Complete evidence in this order:

1. Interview 8–12 serious repeaters, 3–5 beginners and 2–3 tutors.
2. Audit a deliberately difficult 250-question sample.
3. Map the sample to a controlled Paper 1 ontology.
4. Build and test the six-screen core-loop prototype with at least five learners.
5. Compare manually targeted drills against random drills.
6. Run a small Telegram/community acquisition smoke test.
7. Score the exit review without overriding critical failures.

## Decision rule

Advance only if the weighted score is at least 75/100, content readiness and core-loop value each score at least 15/20, and no critical risk remains open.
