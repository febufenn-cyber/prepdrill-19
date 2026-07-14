# Phase 7 Blind Spots

- A client timer can pause, drift, or be manipulated; the deadline is server-owned.
- Autosave retries can duplicate or reorder responses without idempotency keys.
- Palette colors are derived state and must never diverge from saved responses.
- A reconnect must restore exact ordinal, selected response, mark state, and deadline.
- The paper manifest must remain immutable after the attempt starts.
- Answer keys and explanations must not appear in any pre-submit payload.
- Forced submission at the deadline must race safely with a learner's final click.
- Post-submit review must reference the exact revision shown, not the latest corrected revision.
- Visual similarity is not enough; keyboard and state-machine behavior require independent testing.