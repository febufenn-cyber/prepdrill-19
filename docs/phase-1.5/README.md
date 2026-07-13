# Phase 1.5 — Corpus Readiness and Launch Gate

Phase 1.5 is the evidence bridge between the content truth layer and learner-facing drills.

## Why this phase comes next

The Phase 1 exit checklist still has unclosed real-corpus work: golden-set population, representative audit, rights and answer verification, mapping agreement, duplicate adjudication, and review-cost measurement. Building Phase 2 before those are complete would hide data risk behind a polished interface.

## Evidence flow

```text
latest canonical revisions
  → immutable corpus fingerprint
  → deterministic stratified audit sample
  → independent review + mapping evidence
  → golden-set/source/validator verification
  → duplicate adjudication
  → per-stratum readiness report
  → immutable launch-gate evaluation
```

## Commands

```bash
python -m prepdrill_content --db content.sqlite3 create-readiness-audit \
  --name paper1-launch-v1 --target 250 --seed paper1-launch-v1

python -m prepdrill_content --db content.sqlite3 readiness-sample AUDIT_RUN_ID

python -m prepdrill_content --db content.sqlite3 ingest-readiness-reviews \
  AUDIT_RUN_ID reviews.jsonl

python -m prepdrill_content --db content.sqlite3 ingest-mapping-labels \
  AUDIT_RUN_ID mapping-labels.jsonl

python -m prepdrill_content --db content.sqlite3 adjudicate-duplicate CANDIDATE_ID \
  --reviewer reviewer@example.com --decision distinct_questions \
  --reason "Different learning objective"

python -m prepdrill_content --db content.sqlite3 readiness-audit-report AUDIT_RUN_ID
python -m prepdrill_content --db content.sqlite3 validate-golden-set data/golden-set/manifest.v1.json
python -m prepdrill_content --db content.sqlite3 evaluate-launch-gate \
  AUDIT_RUN_ID data/golden-set/manifest.v1.json \
  --thresholds configs/phase15.default-thresholds.json
```

## Important behavior

- Audit samples pin exact revision IDs and semantic hashes.
- Corpus changes do not silently reuse an old pass; they mark the audit stale.
- Reviews and mapping labels are append-only. The latest value per reviewer is used for reporting.
- Aggregates cannot hide a failing unit or question type because the gate applies stratum floors.
- Duplicate decisions are recorded, but the tool never automatically destroys or merges content.
- An empty or fixture-only golden set cannot pass the production gate.
