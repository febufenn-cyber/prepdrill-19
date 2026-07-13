# Prepdrill

> Daily adaptive drills for UGC NET aspirants, built from verified previous-year questions and personalized around actual weaknesses.

Prepdrill is a practice-first learning system. Its job is not merely to serve questions: it converts learner mistakes into a trustworthy next study action.

## Current status

- **Phase 0 — Strategic foundation:** merged into `main`.
- **Phase 1 — Content truth layer:** merged into `main`.
- **Phase 1.5 — Corpus readiness and launch gate:** implemented; real production evidence collection remains open.
- **Phase 2 — Learner drill runtime:** blocked until a current real-corpus gate evaluation passes.

Start here:

- [`docs/phase-0/README.md`](docs/phase-0/README.md) — product and evidence foundation
- [`PHASE_1_BUILD_CONTRACT.md`](PHASE_1_BUILD_CONTRACT.md) — Phase 1 content contract
- [`docs/phase-1/README.md`](docs/phase-1/README.md) — content truth-layer architecture
- [`PHASE_15_BUILD_CONTRACT.md`](PHASE_15_BUILD_CONTRACT.md) — binding corpus-readiness contract
- [`docs/phase-1.5/README.md`](docs/phase-1.5/README.md) — audit and launch-gate workflow
- [`docs/phase-1.5/BLIND_SPOTS.md`](docs/phase-1.5/BLIND_SPOTS.md) — move-order and failure analysis
- [`docs/phase-1.5/PHASE_15_EXIT_CHECKLIST.md`](docs/phase-1.5/PHASE_15_EXIT_CHECKLIST.md) — software and real-evidence gates

## Product wedge

- **Initial exam:** UGC NET Paper 1
- **Initial learner:** serious repeat aspirants who practise but cannot reliably identify what to revise next
- **Core loop:** drill → diagnose → explain → target → re-check
- **Expansion:** English Paper 2 only after Paper 1 evidence gates pass

## Architecture progression

```text
Phase 1
source evidence
  → immutable raw batch
  → deterministic normalisation
  → versioned canonical revision
  → automated validation
  → reviewed published snapshot

Phase 1.5
latest revision fingerprint
  → stratified 250-question audit
  → independent evidence and mapping labels
  → 100-question golden set verification
  → duplicate adjudication
  → fail-closed launch gate

Phase 2, only after the gate passes
published snapshot
  → drill session
  → append-only learner attempts
  → diagnosis and targeted re-check
```

The reference implementation is dependency-free Python + SQLite for deterministic tests. Production migrations target Supabase Postgres with separate raw, core, review, and public boundaries. Readiness evidence remains internal and is not exposed to learner roles.

## Run the content and readiness layers

```bash
python3 -m unittest discover -s tests -v
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 init-db
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 load-taxonomy taxonomy/paper1.v1.json
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 import tests/fixtures/phase1_valid.jsonl --source-document-id fixture-doc-001
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 readiness-report
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 create-readiness-audit --name paper1-launch-v1 --target 250
```

## Non-negotiable boundaries

- Raw imports never flow directly into learner-facing reads.
- Canonical questions, revisions, source occurrences, and public snapshots have separate identities.
- Corrections create new semantic revisions; they do not rewrite historical learner-visible content.
- AI cannot silently change or directly publish canonical answers.
- Missing assets, unresolved rights, unverified answers, disputes, or review-tier records fail publication.
- Corpus audits pin exact revision hashes and become stale when the corpus changes.
- Aggregate metrics cannot hide a failing unit or question type.
- Duplicate candidates are never destructively merged without a recorded human decision.
- Phase 2 does not begin until a real launch corpus returns `passed: true` under the current Phase 1.5 gate.
