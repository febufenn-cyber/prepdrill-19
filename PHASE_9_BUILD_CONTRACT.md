# Phase 9 Build Contract — Retention, Reports, and Consent-Based Communication

## Goal

Help learners maintain useful study continuity without manipulative streaks, misleading reports, duplicate notifications, or communication without explicit consent.

## Required software

- meaningful-learning streaks that require completed scored work and do not count empty sessions;
- exact weekly reports reconciled to immutable attempts, concept states, and completed plans;
- error notebook entries pinned to exact attempts and revisions;
- exam countdown and daily-plan reminders as derived, non-authoritative views;
- per-channel consent, unsubscribe, quiet hours, timezone, frequency caps, and message deduplication;
- provider-neutral Telegram/WhatsApp/email adapters that cannot send when policy blocks delivery;
- immutable communication decisions and outbound queue records;
- no notification unless it points to a meaningful learner action;
- evaluator covering timezone edges, quiet hours, unsubscribe, frequency, deduplication, report reconciliation, and streak integrity;
- all inherited workflows green.

## Non-goals

- sending live messages without credentials and explicit activation;
- treating app opens or empty sessions as learning streak activity;
- modifying attempts or mastery through notification delivery;
- claiming retention improvement without real cohort evidence.

## Acceptance tests

Completed scored activity advances streaks while empty/incomplete sessions do not; weekly reports exactly reconcile attempts; error notebook entries preserve revision identity; quiet hours work across midnight and timezones; unsubscribed channels never queue; frequency caps and idempotency prevent duplicates; messages require a meaningful action; adapters remain no-op without activation; and all inherited suites remain green.