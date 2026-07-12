# Golden Evaluation Set

The golden set is a permanent, versioned regression corpus—not a convenient random sample.

## Target composition

100 reviewed UGC NET Paper 1 questions spanning:

- all units;
- direct MCQ, assertion/reason, matching, passage, table, calculation, multi-statement and asset-dependent formats;
- known extraction failures;
- duplicate/near-duplicate cases;
- ambiguous or disputed examples kept outside publication tests;
- mobile rendering edge cases.

## Required files when populated

- `questions.jsonl`
- `assets/`
- `manifest.json`
- `expected-audit.json`
- `REVIEW_LOG.md`

## Rules

- Every item has provenance and answer evidence.
- Changes require reviewer identity, reason and version increment.
- Test code may depend on IDs but not on mutable display order.
- The set evaluates import, validation, rendering, explanation consistency and migrations.
- Copyright-sensitive source files must not be committed unless repository access and rights permit it.
