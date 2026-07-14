# Phase 7 Build Contract — Full Mock Exam and NTA-Style Simulation

## Goal

Provide authentic full-paper and previous-year mock behavior through immutable paper manifests, server-authoritative timing, lossless response state, exact scoring, and revision-pinned post-submit review.

## Required software

- immutable ordered mock manifests containing exact published revisions and answer keys;
- server-owned start/deadline timestamps and remaining-time calculation;
- NTA-style response states: not visited, not answered, answered, marked for review, answered and marked;
- Save & Next, Mark for Review, Clear Response, autosave, reconnect, and forced-submit behavior;
- idempotent response updates and final submission;
- synchronized palette derived from server response state;
- exact scoring and timing analysis;
- no answer or explanation leakage before submission;
- post-submit review tied to the exact revision shown;
- keyboard command mapping and deterministic evaluator.

## Non-goals

- trusting a client timer or client score;
- changing paper order after an attempt starts;
- rewriting responses after final submission;
- claiming visual parity with the live NTA site without real-device review.

## Acceptance tests

Manifest order/count replay exactly; palette transitions match responses; retries are idempotent; reconnect preserves state; clear/mark/save transitions are correct; deadline forces submission; duplicate submission is safe; pre-submit payloads hide answers; score is exact; review uses pinned revisions; and all inherited workflows remain green.
