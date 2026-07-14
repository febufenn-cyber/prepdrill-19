# Phase 8 Build Contract — Product Quality, Security, Privacy, and Observability

## Goal

Harden Prepdrill before public beta with fail-closed access controls, privacy-safe telemetry, replay and abuse resistance, measurable reliability budgets, verified backup/restore, and operational kill switches.

## Required software

- explicit security control and data-classification registry;
- ownership/role access decisions that deny unknown actions and cross-user access;
- structured log sanitization for secrets, tokens, answers, email, phone, and sensitive learner fields;
- deterministic replay protection and scoped rate limiting;
- safe input validation for identifiers, search text, and structured payloads;
- latency/error-budget evaluation using p50/p95/p99 and failure rate;
- checksummed backup, restore, corruption detection, and rollback rehearsal;
- auditable feature kill switches with safe defaults;
- evaluator covering IDOR, secret leakage, injection-shaped input, replay, rate limits, restore, budgets, and switches;
- all inherited workflows green.

## Non-goals

- claiming an external penetration test;
- storing production secrets in the repository;
- logging raw answers, auth tokens, private explanations, or sensitive learner content;
- allowing observability failure to break core practice;
- treating synthetic load tests as production capacity evidence.

## Acceptance tests

Cross-user access and unknown actions fail; permitted self-read succeeds; sensitive fields are redacted recursively; replayed mutations are rejected; rate limits are scoped and recover after the window; hostile text is treated as data; backup restore matches the source checksum and corrupted backups fail; reliability budgets pass/fail deterministically; kill switches default safely and audit changes; and all inherited suites remain green.