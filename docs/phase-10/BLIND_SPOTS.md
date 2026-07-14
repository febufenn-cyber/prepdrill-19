# Phase 10 Blind Spots

- Payment redirects and client purchase flags are not authoritative evidence.
- Webhooks can arrive duplicated, delayed, out of order, or after a refund.
- A reused provider event ID with a changed payload is a collision, not an idempotent retry.
- Cancellation and refund are different: cancellation may preserve paid access until period end, while refund or chargeback may revoke it.
- Provider outages should not immediately destroy an otherwise valid entitlement.
- Missing webhooks require provider-snapshot reconciliation, not manual state edits.
- Sandbox and live secrets must never be interchangeable.
- Entitlement expiry must not delete attempts, reports, mastery, or explanations.
- A successful evaluator does not authorize real charges or prove commercial demand.