# Prepdrill

> Daily adaptive drills for UGC NET aspirants, built from verified previous-year questions and personalized around actual weaknesses.

Prepdrill is a practice-first learning system. Its job is not merely to serve questions: it converts learner mistakes into a trustworthy next study action.

## Current status

- **Phase 0 — Strategic foundation:** implemented in draft PR #1.
- **Phase 1 — Content truth layer:** implemented on `agent/phase-1-truth-layer`, stacked on Phase 0.
- **Phase 1 corpus-readiness evidence:** still open; real 100-question golden-set selection and 250-question audit cannot be fabricated from the blueprint-only repository.

Start here:

- [`docs/phase-0/README.md`](docs/phase-0/README.md) — product and evidence foundation
- [`PHASE_1_BUILD_CONTRACT.md`](PHASE_1_BUILD_CONTRACT.md) — binding Phase 1 scope
- [`docs/phase-1/README.md`](docs/phase-1/README.md) — implemented truth-layer architecture and commands
- [`docs/phase-1/PHASE_1_EXIT_CHECKLIST.md`](docs/phase-1/PHASE_1_EXIT_CHECKLIST.md) — software and corpus exit gates
- [`schemas/question.v1.schema.json`](schemas/question.v1.schema.json) — canonical structured revision contract
- [`supabase/migrations/001_phase1_content.sql`](supabase/migrations/001_phase1_content.sql) — internal/public schema and RLS boundary

## Product wedge

- **Initial exam:** UGC NET Paper 1
- **Initial learner:** serious repeat aspirants who practise but cannot reliably identify what to revise next
- **Core loop:** drill → diagnose → explain → target → re-check
- **Expansion:** English Paper 2 only after Paper 1 evidence gates pass

## Phase 1 architecture

```text
source evidence
  → immutable raw batch
  → deterministic normalisation
  → versioned canonical revision
  → automated validation findings
  → human/source review
  → immutable published snapshot
  → public read boundary
```

The reference implementation is dependency-free Python + SQLite for deterministic tests. The production migration targets Supabase Postgres with separate `content_raw`, `content_core`, `content_review`, and `content_public` schemas. Learner roles receive access only to active published snapshots.

## Run the truth layer

```bash
python3 -m unittest discover -s tests -v
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 init-db
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 load-taxonomy taxonomy/paper1.v1.json
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 import tests/fixtures/phase1_valid.jsonl --source-document-id fixture-doc-001
python3 -m prepdrill_content --db /tmp/prepdrill.sqlite3 readiness-report
```

## Non-negotiable boundaries

- Raw imports never flow directly into learner-facing reads.
- Canonical questions, revisions, source occurrences, and public snapshots have separate identities.
- Corrections create new semantic revisions; they do not rewrite historical learner-visible content.
- AI cannot silently change or directly publish canonical answers.
- Missing assets, unresolved rights, unverified answers, disputes, or review-tier records fail publication.
- Phase 2 does not begin until a real launch corpus passes the content-readiness gate.
