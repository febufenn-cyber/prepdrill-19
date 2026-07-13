# Phase 2 Blind Spots and Countermoves

## 1. A green synthetic evaluator can be mistaken for corpus readiness

**Risk:** engineering passes while production content remains unreviewed.

**Countermove:** session creation requires a named authorization derived from a current real Phase 1.5 gate. The evaluator cannot create production authorization.

## 2. Correct-answer leakage

**Risk:** session APIs accidentally expose `correct_option_id` or reviewed explanations before submission.

**Countermove:** learner session payloads explicitly remove both fields. Answer-bearing reads are internal-only.

## 3. Snapshot drift during a session

**Risk:** a correction changes what the learner saw after the fact.

**Countermove:** session items pin the published snapshot ID and payload hash. Attempts retain the same hash.

## 4. Retry storms double-count attempts

**Risk:** mobile retries create multiple attempts and inflate scores/mastery.

**Countermove:** globally unique idempotency keys plus one-attempt-per-session-item constraints.

## 5. Adaptive feedback loops

**Risk:** one early mistake traps a learner in a narrow concept forever.

**Countermove:** mixed mode, unseen-concept bonus, deterministic coverage, novelty penalty, bounded re-check priority, and explicit evaluator targeting thresholds.

## 6. False precision in mastery

**Risk:** a decimal score is treated as a scientifically calibrated ability estimate.

**Countermove:** expose attempt count and uncertainty; document the model as an interpretable heuristic pending psychometric calibration.

## 7. Hallucinated explanations

**Risk:** an AI produces persuasive but unsupported reasoning.

**Countermove:** runtime explanations are published-reviewed artifacts with source references. Missing evidence returns `unavailable`.

## 8. Stale readiness approval

**Risk:** content changes after approval while sessions continue.

**Countermove:** every new session recomputes the latest-revision corpus fingerprint and locks on mismatch.

## 9. Direct client score manipulation

**Risk:** a learner writes `correct=true`, mastery, or streak values directly.

**Countermove:** production RLS grants learner reads but no direct writes to attempts, scores, mastery, re-checks, explanations, or activity. Service logic derives them.

## 10. Retired content mid-session

**Risk:** a question is retired after a session starts.

**Countermove:** no new sessions select it, but the immutable historical snapshot remains available for the existing session and audit trail.

## 11. Re-check overload

**Risk:** every mistake creates an unmanageable queue.

**Countermove:** one queue entry per learner and snapshot, replacement on new failure, priority bounds, and completion on a correct re-attempt.

## 12. Evaluator overfitting

**Risk:** implementation is changed to pass one happy-path fixture.

**Countermove:** the evaluator uses adversarial invariants and independent runtime tests. Production outcome experiments remain required after activation.

## 13. Time and streak gaming

**Risk:** clients forge timestamps or repeatedly resubmit.

**Countermove:** production adapters must supply server time; attempts are idempotent and daily activity is derived from immutable attempts.

## 14. Privacy leakage

**Risk:** one learner reads another learner's sessions or diagnosis.

**Countermove:** Supabase policies scope all learner-readable runtime tables to `auth.uid()` through ownership joins.

## 15. Concurrency races

**Risk:** simultaneous submissions compete for one item.

**Countermove:** unique database constraints decide the winner; subsequent conflicting submissions fail without mutating the first attempt.
