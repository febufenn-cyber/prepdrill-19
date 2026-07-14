# Prepdrill Remaining Phases and Autonomous Build Plan

**Baseline:** Phases 0, 1, 1.5 software, and 2 software/evaluator are merged into `main`. Production activation remains fail-closed until a real current corpus gate is authorized by a named owner.

## Executive decision

There are **12 planned remaining phases: Phase 3 through Phase 14**.

- **First trustworthy paid launch:** Phases 3-10.
- **Scale and expansion:** Phases 11-14.
- Software may be implemented behind fail-closed gates when real credentials or evidence are absent. Production authorization, payments, outbound messaging, rights decisions, or corpus claims must never be fabricated.

## `build` command contract

When the user says **`build`**, execute every incomplete phase in numerical order without asking for repeated confirmation. For each phase:

1. Read current `main`, this plan, all prior phase contracts, migrations, evaluators, and CI workflows.
2. Confirm the previous phase merge commit exists on `main` and inherited workflows are green.
3. Create `agent/phase-N-slug` from the exact current `main` SHA.
4. Create `PHASE_N_BUILD_CONTRACT.md`, blind-spot analysis, evaluator specification, and exit checklist **before implementation code**.
5. Verify the phase does not duplicate, bypass, or weaken existing truth, readiness, runtime, identity, or RLS boundaries.
6. Implement in small, independently reviewable modules.
7. Add deterministic unit, integration, adversarial, migration, contract, and regression tests. Every phase gets a phase-specific evaluator.
8. Run the full inherited test matrix plus the new evaluator. Red CI must be fixed; tests may not be weakened to obtain green status.
9. Open a PR to `main` with scope, migrations, evaluator results, activation gates, and exact head SHA.
10. Squash-merge only when GitHub reports mergeable and every required workflow succeeds.
11. Confirm the merged PR, exact `main` SHA, changed-file counts, migrations, activation gates, and remaining external blockers.
12. Continue automatically to the next incomplete phase unless a hard stop applies.

Optional narrower commands:

- `build next` — implement only the next incomplete phase.
- `build phase N` — implement one named phase while preserving dependencies and fail-closed gates.

### Hard stops

A hard stop applies when an irreversible action would affect real users or production data without policy approval; required live credentials or external approvals are unavailable; a real legal/rights decision or human evidence is required; or a failing invariant cannot be resolved without weakening an earlier boundary.

A hard stop blocks **activation**, not necessarily safe software implementation. Code may still be completed and merged behind a disabled feature flag or authorization gate.

## Phase map

| Phase | Name | Roadmap role |
|---:|---|---|
| 3 | Real Corpus Activation and Data Migration | Required for production activation |
| 4 | Production Application, API, and Identity Sync | Required for first learner launch |
| 5 | Grounded Explanation Intelligence and Review Operations | Required for differentiated launch |
| 6 | Adaptive Daily Plan and Mastery Calibration | Required for adaptive-product promise |
| 7 | Full Mock Exam and NTA-Style Simulation | Required for exam-readiness launch |
| 8 | Product Quality, Security, Privacy, and Observability | Required before public beta |
| 9 | Retention, Reports, and Consent-Based Communication | Required for retention proof |
| 10 | Monetization, Entitlements, and Billing Safety | Required for paid launch |
| 11 | Growth, SEO, Telegram, and Attribution | Scale after product proof |
| 12 | Admin, Content Operations, and Institute Console | Second business model |
| 13 | Controlled Content Scaling and Generated-Question Quarantine | Scale content only after trust proof |
| 14 | Paper 2 English, Native Clients, and Multi-Exam Platformization | Expansion after Paper 1 gates |

## Phase contracts

### Phase 3 — Real Corpus Activation and Data Migration

**Goal:** move from fixtures to a current, audited UGC NET Paper 1 corpus and issue a named launch authorization.

**Deliver:** fresh-source ingestion manifests; reconciliation for questions, contexts, assets, keys, taxonomy, and source documents; a real 100-question golden set; a real 250-question stratified audit; rights/provenance/answer/rendering/mapping/duplicate/review-cost evidence; current gate evaluation; named-owner authorization; reversible import batches.

**Evaluator:** manifest count reconciliation; zero orphaned contexts/assets; golden hash/source/validator replay; unit/type quality floors; drift invalidation; negative test preventing legacy sample/generated data from entering the launch subset.

**Exit:** real gate passes, named authorization matches the current corpus fingerprint, and no blocking content or rights issue remains.

### Phase 4 — Production Application, API, and Identity Sync

**Goal:** expose the verified runtime through a fast application and stable API with guest-first onboarding and correct cross-device recovery.

**Deliver:** production API; responsive web/PWA; quick/topic/diagnostic/review/weakness/recheck flows; deterministic guest-to-account merge; correct existing-account loading; complete structured-question renderer; accessibility, keyboard, interrupted-session recovery, and privacy-safe instrumentation.

**Evaluator:** guest → attempts → sign-in → merge → second device; account-collision and wrong-name cases; visual fixtures for every question type; API auth/idempotency/retry tests; client tampering cannot alter score, mastery, answers, or publication truth.

**Exit:** Phase 2 invariants remain green through the real API and production activation stays locked when Phase 3 authorization is absent or stale.

### Phase 5 — Grounded Explanation Intelligence and Review Operations

**Goal:** generate useful explanations without allowing AI to alter official truth or become a practice dependency.

**Deliver:** grounded generation from exact revision, answer evidence, syllabus concept, and source context; distractor-specific layers; model routing, caching, versioning, cost limits, retries, explicit unavailable state; disagreement review queue; immutable explanation revisions; cross-format evaluation set.

**Evaluator:** answer-consistency, grounding, unsupported-claim, distractor-usefulness, cache/version regression, cost/latency, and total AI-provider outage tests.

**Exit:** no high-severity contradiction in the golden explanation set; every visible explanation is approved or unavailable; AI cannot write canonical answers, publication state, or mastery.

### Phase 6 — Adaptive Daily Plan and Mastery Calibration

**Goal:** create calibrated daily study plans without repetitive or misleading targeting.

**Deliver:** versioned mastery using correctness, time, difficulty, recency, confidence, hints, answer changes, and evidence strength; daily blend of weak/due/recent/mixed/challenge/confidence-repair items; diversity/exposure controls; learner-visible selection rationale; shadow model comparisons.

**Evaluator:** simulated learner trajectories; calibration/ranking/diversity/repetition/recheck conversion; anomalous-attempt resistance; no unauthorized experimental influence; regression against Phase 2 targeting.

**Exit:** reproducible, auditable recommendations meeting calibration and diversity gates.

### Phase 7 — Full Mock Exam and NTA-Style Simulation

**Goal:** provide authentic full-paper and previous-year mocks while preserving the fast practice loop.

**Deliver:** paper builder by date/year/month/shift/set; timer, palette, Save & Next, Mark for Review, Clear Response, sections, autosave, reconnect, forced submit; immutable mock snapshots; post-submit result, timing analysis, diagnosis, and exact-revision review; desktop-first exam mode.

**Evaluator:** state-machine transitions; timer/reconnect/deadline/duplicate-submit boundaries; paper manifest order/count replay; no pre-submit answers; visual and keyboard palette/context tests.

**Exit:** exact scoring, no lost responses, synchronized palette/server state, and review tied to the shown revisions.

### Phase 8 — Product Quality, Security, Privacy, and Observability

**Goal:** harden the system before growth and payments make defects expensive.

**Deliver:** threat model, retention/privacy implementation, least privilege, abuse controls, privacy-safe logs, traces/metrics/error budgets, load and soak tests, backups/restores/rollback, incident runbooks, accessibility and performance budgets.

**Evaluator:** RLS/IDOR matrix; dependency/secret/injection/replay/rate-limit tests; restore rehearsal; migration rollback; p50/p95/p99 load gates; prohibited-field log scanning.

**Exit:** no critical/high security finding, demonstrated restore and rollback, core flows within availability/latency/accessibility targets, and defined kill switches.

### Phase 9 — Retention, Reports, and Consent-Based Communication

**Goal:** create useful study continuity without manipulative streaks or spam.

**Deliver:** daily plans, meaningful-learning streak and recovery, weekly reports, exam countdown, error notebook, consent/preference center, quiet hours, frequency caps, unsubscribe, Telegram/WhatsApp adapters, retention analytics.

**Evaluator:** timezone/quiet-hour/frequency/unsubscribe/dedup tests; report reconciliation; no message without meaningful action; consent audit; empty sessions cannot inflate streaks.

**Exit:** every message is consented, explainable, deduplicated, rate-limited, and exactly reconciled to learner evidence.

### Phase 10 — Monetization, Entitlements, and Billing Safety

**Goal:** charge for demonstrated value while keeping entitlement state correct.

**Deliver:** plan catalog, free limits, trials, entitlements, grace, cancellation, refunds, invoices, Razorpay sandbox/live configuration, signed idempotent webhooks, reconciliation, post-value paywalls, revenue metrics.

**Evaluator:** duplicate/delayed/missing/reversed/forged/replayed webhooks; provider reconciliation; refund/cancel/grace boundaries; billing cannot delete learner history; sandbox purchase flow.

**Exit:** deterministic auditable entitlements, safe reconciliation, no live payment without explicit activation and secrets, and safe degradation during provider outages.

### Phase 11 — Growth, SEO, Telegram, and Attribution

**Goal:** create acquisition loops from public educational value to personalized practice.

**Deliver:** rights-cleared public concept/question pages, canonical metadata, Telegram daily question deep links, creator/YouTube diagnostics, attribution surviving guest merge, referral/experiment framework with abuse controls.

**Evaluator:** publication/rights gate for indexable content; deep-link attribution continuity; bot/referral abuse; canonical/robots/sitemap checks; metrics tied to activation, retained learning, and conversion.

**Exit:** no blocked content is indexed, attribution is learner-safe, experiments have predeclared guardrails, and every channel has a kill switch.

### Phase 12 — Admin, Content Operations, and Institute Console

**Goal:** scale quality operations and add a controlled B2B surface without weakening privacy.

**Deliver:** internal content console; tenant/role/cohort/assignment/aggregate-report model; privacy-preserving learner views; dry-run/approval/audit/rollback bulk actions; exports and retention controls; content-operation SLA metrics.

**Evaluator:** tenant isolation across UI/API/SQL/export/jobs/cache; role escalation; bulk rollback; admin cannot bypass Phase 1 gates; institute users cannot access unapproved personal data.

**Exit:** proven tenant isolation, audited reversible mutations, truth gates remain authoritative, and minimum-cohort privacy rules are enforced.

### Phase 13 — Controlled Content Scaling and Generated-Question Quarantine

**Goal:** increase practice coverage without contaminating official truth or mastery.

**Deliver:** concept-controlled variant pipeline with independent solve, second-model verification, similarity/difficulty checks, human review, experimental quarantine, psychometric monitoring, complaint/retirement flow, lineage, and generation economics.

**Evaluator:** solver agreement; answer consistency; ambiguity/duplicate/leakage/difficulty/concept drift; shadow release; no experimental content in mocks/official archives; cost-per-approved-item gates.

**Exit:** experimental/canonical isolation, human-approved promotion with provenance, no default mastery influence, and automatic stop rules when quality or economics fail.

### Phase 14 — Paper 2 English, Native Clients, and Multi-Exam Platformization

**Goal:** expand without rebuilding the truth, runtime, evaluator, or business logic for every subject and client.

**Deliver:** exam/subject configuration, syllabus/taxonomy/content/policy packs; Paper 2 English ingestion and separate gate; shared web/iOS/Android contracts; onboarding-first sign-in and correct account sync; native renderer/mock parity; expansion scorecard.

**Evaluator:** cross-subject isolation; web/iOS/Android score/state parity; Paper 2 gate equivalent to Phase 3; cross-client merge/recovery; predeclared kill/scale decision.

**Exit:** Paper 2 English has its own current authorization, all clients pass the same runtime contract, Paper 1 trust/retention/economics remain healthy, and no further exam launches without a new approved plan.

## Per-phase Git confirmation

After each phase report:

- PR link and phase name.
- Verified branch head SHA.
- Every workflow and conclusion.
- Squash-merge SHA on `main`.
- Changed files, additions, and deletions.
- Migrations, feature flags, and activation gates.
- What is software-complete.
- What remains blocked by real evidence, credentials, deployment, legal review, or human approval.
- The next phase starting automatically.

## Global invariants

- Verified official/licensed/authored content remains authoritative over AI output.
- AI never silently changes canonical answers or publication truth.
- Every attempt references the exact immutable published snapshot shown.
- Experimental/generated questions are isolated and cannot affect mastery by default.
- `auth.users.id` owns signed-in learner progress; guest merge is audited and collision-safe.
- Core practice works when AI, billing, messaging, or analytics providers are unavailable.
- Raw/review/internal schemas are never exposed to learner roles.
- Fresh source manifests—not legacy sample, repaired, or generated files—are the corpus source of truth.
- No second public exam launches before Paper 1 trust, retention, economics, and operations gates pass.

## Roadmap completion

The roadmap is complete when Phase 14 is software-complete, all inherited and phase evaluators are green, Paper 1 has an active real-corpus authorization, the paid launch path is operational, Paper 2 English has a separate passed gate, native clients satisfy the shared contract, and every activation requiring external credentials or human evidence is explicitly confirmed rather than assumed.
