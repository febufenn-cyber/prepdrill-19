# Phase 2 Exit Checklist

## Software

- [x] Runtime requires a current named launch authorization.
- [x] Corpus drift locks new sessions.
- [x] Only active published snapshots can be selected.
- [x] Adaptive, mixed, and re-check modes are deterministic.
- [x] Pre-attempt payloads hide answers and explanations.
- [x] Session items and attempts pin immutable snapshot hashes.
- [x] Attempt submissions are idempotent and exactly once per item.
- [x] Scores are server-derived.
- [x] Mastery, uncertainty, diagnosis, and target concepts are implemented.
- [x] Incorrect/skip/timeout outcomes schedule re-checks.
- [x] Correct re-checks clear pending queue entries.
- [x] Explanations fail closed without reviewed source grounding.
- [x] Daily activity and streak accounting are implemented.
- [x] Runtime attempts, items, explanations, events, and evaluations are immutable.
- [x] Adversarial evaluator covers the full learner loop.
- [x] SQLite, Supabase, OpenAPI, CLI, schemas, tests, and CI are included.

## Production activation

- [ ] A real current Phase 1.5 evaluation has `passed: true`.
- [ ] A named owner has reviewed and authorized that evaluation.
- [ ] Production service credentials and RLS have been verified.
- [ ] Server-controlled timestamps and idempotency keys are wired in the client adapter.
- [ ] Real device rendering is validated for all supported question types.
- [ ] Load and concurrency tests are run against the deployed API.
- [ ] Accessibility and screen-reader testing is complete.
- [ ] Privacy, retention, deletion, and support procedures are approved.
- [ ] A real learner pilot measures completion, explanation usefulness, and re-check lift.

Phase 2 software can be merged while production activation remains locked. No production learner session should be created until every applicable activation item is complete.
