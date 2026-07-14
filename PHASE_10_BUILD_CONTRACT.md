# Phase 10 Build Contract — Monetization, Entitlements, and Billing Safety

## Goal

Charge only after demonstrated value while keeping learner entitlements deterministic, auditable, provider-reconcilable, and safe under duplicate, delayed, reversed, forged, or missing payment events.

## Required software

- versioned plan catalog, free limits, trials, paid periods, grace, cancellation, refund, and expiration states;
- entitlements derived from immutable billing events, never client flags;
- signed webhook verification, replay protection, idempotency, event ordering, and provider-object version checks;
- invoice/payment/subscription reconciliation against provider snapshots;
- sandbox and live modes with separate secrets and explicit activation gates;
- post-value paywall decisions that do not delete learner history;
- provider outage behavior that preserves current safe entitlement until reconciliation policy decides otherwise;
- refund and chargeback revocation without rewriting historical attempts;
- evaluator covering duplicate, delayed, missing, forged, replayed, reversed, cancel, grace, refund, and provider outage paths;
- all inherited workflows green.

## Non-goals

- storing real payment secrets in the repository;
- activating live charges without explicit owner authorization;
- trusting redirect URLs or client purchase claims;
- deleting learner progress when entitlement ends;
- claiming real revenue or successful provider certification.

## Acceptance tests

Forged signatures fail; exact duplicate events are idempotent; reused event IDs with changed payloads fail; stale events cannot override newer state; completed payments grant the expected plan; cancellation preserves access through paid end; grace is bounded; refund/chargeback revoke future premium access without deleting history; missing webhooks are repaired by reconciliation; sandbox/live secrets cannot mix; live mode stays disabled without explicit activation; and all inherited suites remain green.