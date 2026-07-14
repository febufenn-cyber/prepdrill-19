# Phase 12 Blind Spots

- Tenant IDs in UI filters do not protect SQL, exports, background jobs, or caches.
- A user can belong to multiple tenants; permissions must be evaluated against the selected tenant membership.
- Aggregate dashboards can re-identify learners when cohorts are too small.
- Institute staff should not see personal details merely because they assigned a drill.
- Assignments must pin immutable published snapshots, not mutable question IDs.
- Bulk actions need a dry-run and independent approval; one-click admin power is an operational vulnerability.
- Rollback should append compensating events instead of deleting audit history.
- Internal admins still cannot override answer, rights, asset, or publication blockers.
- Export files can become a secondary data leak and need field allow-lists, tenant fingerprints, and retention state.