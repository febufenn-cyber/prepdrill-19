# Phase 1.5 Exit Checklist

## Software

- [x] Audit runs pin a corpus fingerprint.
- [x] Sampling is deterministic and stratified by unit, type, and tier.
- [x] Sample reviews are append-only and validate typed evidence fields.
- [x] Review time is measured and projected to 1,000 questions.
- [x] Independent mapping labels produce pairwise agreement and Cohen's kappa.
- [x] Golden entries verify revision hash, source checksum, and validator codes.
- [x] Duplicate adjudication is human-controlled and audited.
- [x] Per-unit and per-type quality floors are enforced.
- [x] Corpus drift invalidates old evidence.
- [x] Launch evaluations store thresholds, metrics, findings, and fingerprints.
- [x] SQLite reference implementation, Supabase migration, CLI, tests, schemas, and CI exist.

## Real corpus evidence

- [ ] At least 250 real latest revisions selected in the audit.
- [ ] Every sampled revision reviewed.
- [ ] 100 real golden-set entries populated and verified.
- [ ] All ten Paper 1 units represented.
- [ ] All supported question types represented.
- [ ] Rights and provenance pass for every reviewed launch item.
- [ ] Answer evidence passes for every reviewed launch item.
- [ ] Rendering passes for every reviewed launch item.
- [ ] No blocking verdict remains.
- [ ] No pending duplicate candidate touches the sample.
- [ ] At least 50 items independently concept-mapped.
- [ ] Minimum pairwise Cohen's kappa is at least 0.80.
- [ ] Review cost per 1,000 questions measured and accepted.
- [ ] At least 100 active published questions form the launch subset.
- [ ] Final gate evaluation returns `passed: true` on the current corpus fingerprint.

Phase 2 stays blocked until the real-corpus section is complete.
