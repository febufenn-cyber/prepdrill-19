# Phase 8 Blind Spots

- RLS policies do not protect code paths that use a privileged service role incorrectly.
- Logs can leak answer keys, tokens, contact details, and learner state even when database access is correct.
- Rate limits must be scoped by actor and operation; one global counter creates denial-of-service risk.
- Idempotency and replay protection are related but not identical: a reused key with different content is an attack.
- SQL-looking or HTML-looking text is not dangerous when treated as data, but unsafe interpolation converts it into code.
- Average latency hides tail failures; p95, p99, and failure rate are separate gates.
- A backup that has never been restored is not evidence of recoverability.
- Kill switches without audit history or safe defaults can become hidden bypasses.
- Synthetic security and load evaluators do not replace an external review or production rehearsal.