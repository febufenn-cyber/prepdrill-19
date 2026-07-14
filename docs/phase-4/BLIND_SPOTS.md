# Phase 4 Blind Spots

- A display-name mismatch is not an account mismatch; authenticated identity owns progress.
- Retried sign-in callbacks can duplicate progress unless merge operations are idempotent.
- A guest linked to one account must never be silently moved to another.
- A second device must load server state, not recreate onboarding state.
- Client applications can forge correctness, score, timing, or mastery fields; the service ignores them.
- Pre-attempt payload filtering must be allow-list based so newly added internal fields cannot leak.
- Rendering plain text alone loses tables, formulas, images, match lists, and accessibility meaning.
- Offline or interrupted flows require immutable request keys and recoverable server state.
- A polished client can accidentally bypass activation locks; flow creation remains server-gated.
