# Prepdrill

> Daily adaptive drills for UGC NET aspirants, built from verified previous-year questions and personalized around actual weaknesses.

Prepdrill is a practice-first learning system. Its job is not merely to serve questions: it converts learner mistakes into a trustworthy next study action.

## Current status

**Phase 0 — Strategic foundation** is implemented on the product-planning track. It defines the first user, content trust rules, learning model, architecture boundaries, analytics, evidence gates, and the Phase 1 build contract.

Start here:

- [`docs/phase-0/README.md`](docs/phase-0/README.md) — Phase 0 index and execution board
- [`PHASE_1_BUILD_CONTRACT.md`](PHASE_1_BUILD_CONTRACT.md) — binding scope for the next implementation phase
- [`schemas/question.schema.json`](schemas/question.schema.json) — canonical question interchange schema
- [`scripts/content_audit.py`](scripts/content_audit.py) — zero-dependency JSON/JSONL corpus validator

## Product wedge

- **Initial exam:** UGC NET Paper 1
- **Initial learner:** serious repeat aspirants who practise but cannot reliably identify what to revise next
- **Core loop:** drill → diagnose → explain → target → re-check
- **Expansion:** English Paper 2 after Paper 1 evidence gates pass

## Architecture direction

`Cloudflare Workers + Hono + Supabase + provider-abstracted AI`

- Supabase Postgres is the source of truth for published content, attempts, learner state, and entitlements.
- Raw imports never flow directly into learner-facing APIs.
- AI may explain or flag conflicts, but cannot silently alter canonical answers.
- Attempts are append-only events so mastery models can be recomputed.

## Phase 0 quality checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/content_audit.py tests/fixtures/valid_questions.jsonl
```

## Original blueprint

The repository began as a Codecademy-shaped interactive exam-practice seed with timed drills, explanations, weakness analysis, streaks, Razorpay, WhatsApp, and authored/licensed question banks. Phase 0 narrows that broad idea into a testable UGC NET opening position before production feature work begins.
