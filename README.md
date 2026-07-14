# Prepdrill

> Daily adaptive drills for UGC NET aspirants, built from verified previous-year questions and personalized around actual weaknesses.

Prepdrill is a practice-first learning system. Its job is not merely to serve questions: it converts learner mistakes into a trustworthy next study action.

## Current status

The complete planned software roadmap is implemented through **Phase 14**.

- **Phase 0:** strategic foundation
- **Phase 1:** content truth layer
- **Phase 1.5:** corpus readiness and launch gate
- **Phase 2:** learner drill runtime and evaluator
- **Phase 3:** real-corpus activation and reversible migration controls
- **Phase 4:** application service, guest-first identity, and account sync
- **Phase 5:** grounded explanation intelligence and review operations
- **Phase 6:** adaptive daily plans and calibrated mastery
- **Phase 7:** immutable NTA-style mock exam runtime
- **Phase 8:** security, privacy, reliability, recovery, and kill switches
- **Phase 9:** meaningful retention, reports, consent, and communication policy
- **Phase 10:** billing, reconciliation, and deterministic entitlements
- **Phase 11:** rights-gated public growth, attribution, referrals, and experiments
- **Phase 12:** tenant-isolated institute and admin operations
- **Phase 13:** generated-content quarantine and shadow promotion
- **Phase 14:** Paper 2/native shared contracts and multi-subject platformization

Software completion is not production activation. Real corpus evidence, rights decisions, provider credentials, deployment, real-user outcomes, security review, payment activation, institute onboarding, generated-content review, Paper 2 authorization, and native-store releases remain explicit external gates.

## Canonical contracts

- [`docs/roadmap/REMAINING_PHASES_AUTONOMOUS_BUILD_PLAN.md`](docs/roadmap/REMAINING_PHASES_AUTONOMOUS_BUILD_PLAN.md)
- [`PHASE_1_BUILD_CONTRACT.md`](PHASE_1_BUILD_CONTRACT.md)
- [`PHASE_15_BUILD_CONTRACT.md`](PHASE_15_BUILD_CONTRACT.md)
- [`PHASE_2_BUILD_CONTRACT.md`](PHASE_2_BUILD_CONTRACT.md)
- [`PHASE_3_BUILD_CONTRACT.md`](PHASE_3_BUILD_CONTRACT.md)
- [`PHASE_4_BUILD_CONTRACT.md`](PHASE_4_BUILD_CONTRACT.md)
- [`PHASE_5_BUILD_CONTRACT.md`](PHASE_5_BUILD_CONTRACT.md)
- [`PHASE_6_BUILD_CONTRACT.md`](PHASE_6_BUILD_CONTRACT.md)
- [`PHASE_7_BUILD_CONTRACT.md`](PHASE_7_BUILD_CONTRACT.md)
- [`PHASE_8_BUILD_CONTRACT.md`](PHASE_8_BUILD_CONTRACT.md)
- [`PHASE_9_BUILD_CONTRACT.md`](PHASE_9_BUILD_CONTRACT.md)
- [`PHASE_10_BUILD_CONTRACT.md`](PHASE_10_BUILD_CONTRACT.md)
- [`PHASE_11_BUILD_CONTRACT.md`](PHASE_11_BUILD_CONTRACT.md)
- [`PHASE_12_BUILD_CONTRACT.md`](PHASE_12_BUILD_CONTRACT.md)
- [`PHASE_13_BUILD_CONTRACT.md`](PHASE_13_BUILD_CONTRACT.md)
- [`PHASE_14_BUILD_CONTRACT.md`](PHASE_14_BUILD_CONTRACT.md)

Each phase has a blind-spot analysis, evaluator specification, exit checklist, tests, production migration, and GitHub Actions workflow.

## Architecture progression

```text
verified source evidence
  → immutable canonical content and revisions
  → representative corpus audit and launch gate
  → readiness-gated drill runtime
  → fresh-corpus activation authorization
  → guest-first application and identity sync
  → grounded reviewed explanations
  → calibrated mastery and daily plans
  → immutable NTA-style mocks
  → security, privacy, recovery, and observability controls
  → consented retention and reports
  → reconciled billing and entitlements
  → rights-gated growth and attribution
  → tenant-isolated institute operations
  → generated-content quarantine
  → separately authorized subjects and shared native contracts
```

The reference implementation is dependency-free Python + SQLite for deterministic verification. Production migrations target Supabase Postgres with separate raw, core, review, public, learner, activation, operations, billing, institute, generated-content, and platform-expansion boundaries.

## Run the complete verification suite

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q prepdrill_content tests
python3 -m prepdrill_content phase2-evaluate
python3 -m prepdrill_content.phase3
python3 -m prepdrill_content.phase4
python3 -m prepdrill_content.phase5
python3 -m prepdrill_content.phase6
python3 -m prepdrill_content.phase7
python3 -m prepdrill_content.phase8
python3 -m prepdrill_content.phase9
python3 -m prepdrill_content.phase10
python3 -m prepdrill_content.phase11
python3 -m prepdrill_content.phase12
python3 -m prepdrill_content.phase13
python3 -m prepdrill_content.phase14
```

## Non-negotiable boundaries

- Raw imports never flow directly into learner-facing reads.
- Canonical questions, revisions, source occurrences, and published snapshots have separate identities.
- AI cannot silently change or directly publish canonical answers.
- Missing assets, unresolved rights, unverified answers, disputes, or review-tier records fail publication.
- Corpus audits pin exact revision hashes and become stale when the corpus changes.
- Production sessions require a current corpus authorization and named owner.
- Authenticated account identity owns merged progress even when onboarding names differ.
- Pre-attempt payloads never expose answers or reviewed explanations.
- Client correctness, score, mastery, entitlement, and publication claims are never trusted.
- Generated candidates remain isolated from official archives, full mocks, public previous-year pages, and mastery by default.
- Institute access is tenant-scoped and small cohorts are privacy-suppressed.
- Billing, communication, growth, experiments, and provider integrations default disabled without explicit activation.
- Paper 2 English requires its own audited corpus fingerprint and named authorization; Paper 1 authorization cannot unlock it.
- Web, iOS, and Android use the same server-owned state and scoring contract.
- Evaluators prove software invariants but never substitute for real legal, corpus, learner-outcome, security, payment, or deployment evidence.
