# Phase 6 Build Contract — Adaptive Daily Plan and Mastery Calibration

## Goal

Turn immutable learner attempts into calibrated, explainable concept state and a reproducible daily plan without repetitive targeting, false precision, or contamination from experimental content.

## Required software

- versioned mastery models using correctness, response time, difficulty, recency, confidence, hints, answer changes, and evidence strength;
- explicit uncertainty and evidence counts;
- bounded handling of anomalous response times and low-quality attempts;
- experimental/generated attempts excluded from default mastery;
- daily blend of weak, due, recent, mixed, challenge, and confidence-repair items;
- concept diversity, exposure limits, deterministic seeds, and learner-visible rationale;
- shadow-model comparison that cannot mutate production state;
- calibration and ranking metrics;
- Phase 6 evaluator and inherited regression suite.

## Non-goals

- claiming human mastery from a single attempt;
- letting generated experimental questions alter production mastery by default;
- using opaque scores without rationale or model version;
- repeating the weakest concept indefinitely;
- fabricating real learner calibration evidence.

## Acceptance tests

Correct/incorrect trajectories move in the expected direction, hints and answer changes weaken evidence, anomalies are bounded, experimental attempts are ignored, plan selection is deterministic and diverse, due and weak items are represented, exposure limits hold, rationales are present, shadow evaluation is read-only, and all inherited workflows remain green.
