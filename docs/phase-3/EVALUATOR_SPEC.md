# Phase 3 Evaluator Specification

The evaluator uses an isolated in-memory SQLite database and the same activation repository used by production code.

It must verify:

- deterministic manifest fingerprints;
- mandatory source roles;
- complete count reconciliation;
- zero orphaned contexts and assets;
- zero fixture, legacy, generated, unresolved-rights, or invalid-source launch items;
- at least 100 golden questions and 250 audited questions;
- a current passed Phase 1.5 gate;
- named-owner authorization;
- automatic authorization invalidation after drift;
- append-only rollback events;
- a minimum evaluator depth of ten independent checks.

A green evaluator means the activation software fails closed. It does not mean the real corpus has passed.
