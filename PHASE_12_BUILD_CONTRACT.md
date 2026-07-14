# Phase 12 Build Contract — Admin, Content Operations, and Institute Console

## Goal

Scale internal quality operations and introduce a privacy-preserving institute surface without allowing tenant leakage, role escalation, bulk-action damage, or administrative bypass of content truth gates.

## Required software

- explicit tenant, membership, role, cohort, assignment, and learner-enrollment boundaries;
- deny-by-default role permissions and tenant ownership checks across reads, mutations, exports, jobs, and caches;
- aggregate institute reports with minimum-cohort privacy and no unapproved personal learner data;
- assignments pinned to approved published snapshots or approved mock manifests;
- content-operation workflows with dry-run, impact preview, separate approval, immutable audit, execution, and compensating rollback;
- admin actions that invoke rather than bypass Phase 1 validation/publication decisions;
- export manifests, retention state, and tenant-scoped fingerprints;
- operational SLA metrics for review queues and publishing throughput;
- Phase 12 evaluator covering tenant isolation, role escalation, cohort privacy, bulk rollback, export boundaries, and content-gate preservation;
- all inherited workflows green.

## Non-goals

- exposing raw learner conversations or unapproved personal data to institutes;
- allowing institute roles to publish or change canonical answers;
- destructive bulk updates without preview and approval;
- creating a visually polished production dashboard without deployment evidence;
- claiming signed institute customers.

## Acceptance tests

Cross-tenant read/write/export/job access fails; role escalation fails; valid tenant admin operations succeed; small cohorts suppress metrics; large cohorts return aggregate-only metrics; assignments reject unpublished content; bulk operations require dry-run and a different approver, record exact before/after state, and roll back through compensating events; exports include only tenant-owned allowed fields; and all inherited suites remain green.