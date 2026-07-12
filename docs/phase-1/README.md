# Phase 1 — Content Truth Layer

Phase 1 turns the Phase 0 trust constitution into executable boundaries.

## Implemented

- immutable, checksummed raw import batches;
- adapter-driven JSON/JSONL import;
- deterministic normalisation into structured content blocks;
- stable canonical IDs and immutable revision IDs;
- separate workflow, issue and validation dimensions;
- per-revision source links and answer claims;
- layered structural and publication validation;
- asset and shared-context resolution;
- exact/near duplicate fingerprints and candidate queue;
- review events with before/after evidence;
- immutable published snapshots;
- a public repository that reads only published snapshots;
- readiness reporting by unit, type, tier, workflow, issue and blocker;
- versioned UGC NET Paper 1 taxonomy;
- Supabase schema separation and RLS boundary;
- CLI, tests and CI.

## Commands

```bash
python -m prepdrill_content --db content.sqlite3 init-db
python -m prepdrill_content --db content.sqlite3 load-taxonomy taxonomy/paper1.v1.json
python -m prepdrill_content --db content.sqlite3 import questions.jsonl --source-document-id nta-2024-june-shift-1
python -m prepdrill_content --db content.sqlite3 readiness-report
python -m prepdrill_content --db content.sqlite3 validate REVISION_ID --publication
```

Publication is deliberately explicit and fails closed. A record must be approved, issue-free, Gold/Silver, rights-cleared, answer-verified, human reviewed and fully verified before a snapshot can be created.

## Evidence still required

The software is implemented, but these cannot be invented from an empty repository:

1. selection and review of 100 real golden-set questions;
2. audit of 250 representative real corpus questions;
3. rights review of actual source documents;
4. concept-mapping agreement measurement;
5. human review-time measurement;
6. identification of a real Gold/Silver launch subset.

Until those artifacts are populated, Phase 1 is technically implemented but its corpus-readiness exit gate remains open.
