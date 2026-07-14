# Phase 9 Blind Spots

- App opens, notification taps, and empty sessions are engagement, not learning evidence.
- Quiet hours frequently cross midnight and must be evaluated in the learner's timezone.
- Unsubscribe must override campaigns, retries, and previously scheduled messages.
- Frequency limits must be scoped by learner, channel, and message category.
- Retried jobs can duplicate messages unless the decision and provider request are idempotent.
- Reports can drift from source attempts if they cache mutable aggregates without reconciliation.
- A message without a concrete due plan, report, re-check, or exam action is noise.
- Provider delivery success does not prove the learner read or benefited from a message.
- Communication adapters must be disabled safely when credentials or activation approval are absent.