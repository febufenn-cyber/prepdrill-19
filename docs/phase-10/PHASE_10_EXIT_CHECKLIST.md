# Phase 10 Exit Checklist

## Software
- [x] Versioned plan catalog and features.
- [x] Entitlement derives from immutable signed provider events.
- [x] Duplicate, replay, payload-collision, and stale-event controls.
- [x] Paid, trial, grace, cancel, refund, chargeback, and expiry states.
- [x] Cancellation preserves paid-period access; refund/chargeback revoke.
- [x] Provider-snapshot reconciliation repairs missing events.
- [x] Provider outage preserves an already valid period.
- [x] Sandbox/live secrets and activation are isolated.
- [x] Post-value paywall decisions.
- [x] Billing state cannot delete learning history.
- [x] Evaluator and inherited workflows pass.

## Live billing evidence
- [ ] Razorpay or selected provider sandbox certification completed.
- [ ] Production secrets configured outside the repository.
- [ ] Named owner explicitly activates live mode.
- [ ] Refund, dispute, tax, invoice, and support processes reviewed.
- [ ] Real reconciliation and revenue metrics monitored.

Software completion does not authorize live charges.