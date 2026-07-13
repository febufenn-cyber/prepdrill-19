# Phase 2 — Learner Drill Runtime and Evaluator

Phase 2 implements the learner-facing practice loop while preserving the trust boundaries built earlier.

## Architecture

```text
current passed readiness evaluation
  → named launch authorization
  → active published snapshots
  → deterministic session selection
  → immutable session items
  → idempotent attempts
  → derived score and mastery
  → reviewed grounded explanation
  → weakness targeting and due re-check
```

The runtime refuses new sessions when the corpus fingerprint no longer matches the authorization. Existing sessions and attempts remain readable because they reference immutable published snapshot IDs and payload hashes.

## Selection modes

- `adaptive`: prioritizes due re-checks, low mastery, and unseen concepts.
- `mixed`: deterministic broad coverage with due re-check priority.
- `recheck`: returns only pending items whose due time has arrived.

Tie-breaking uses a stable hash of the caller-provided seed and published snapshot ID. Identical learner state and seed therefore produce identical selection.

## Attempts and scoring

Attempts are append-only and keyed by a client-supplied idempotency key. A replay returns the original attempt. A second key for the same session item is rejected. The server derives correctness from the immutable published snapshot and updates the session score from stored attempts.

## Mastery

The reference model uses a beta-smoothed posterior:

```text
mastery = (correct + 1) / (attempts + 2)
uncertainty = 1 / sqrt(attempts + 1)
```

This is intentionally interpretable and conservative. It is not presented as a calibrated psychometric ability estimate.

## Explanations

The runtime does not invent explanations. A response is `grounded` only when the published revision contains:

- reviewed summary;
- review timestamp;
- at least one source reference.

Otherwise the response is `unavailable` and names that limitation.

## Evaluator

`Phase2Evaluator` creates an isolated synthetic corpus and runs the actual runtime implementation through adversarial journeys. It tests gate enforcement, determinism, publication isolation, idempotency, scoring, mastery direction, targeting, re-checks, explanation grounding, diagnosis, and drift lockdown.

```bash
python3 -m prepdrill_content phase2-evaluate
```

The evaluator validates software behavior only. It does not replace the real Phase 1.5 corpus gate or real learner outcome experiments.

## Operator commands

```bash
python3 -m prepdrill_content --db prepdrill.sqlite3 phase2-authorize-launch GATE_ID --owner OWNER --reason REASON
python3 -m prepdrill_content --db prepdrill.sqlite3 phase2-create-session LEARNER_ID --size 10 --seed daily
python3 -m prepdrill_content --db prepdrill.sqlite3 phase2-submit SESSION_ID 0 --idempotency-key UUID --selected-option-id A
python3 -m prepdrill_content --db prepdrill.sqlite3 phase2-diagnose LEARNER_ID
python3 -m prepdrill_content --db prepdrill.sqlite3 phase2-explain ATTEMPT_ID
python3 -m prepdrill_content --db prepdrill.sqlite3 phase2-streak LEARNER_ID
```
