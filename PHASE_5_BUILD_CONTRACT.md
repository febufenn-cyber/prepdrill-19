# Phase 5 Build Contract — Grounded Explanation Intelligence and Review Operations

## Goal

Produce useful distractor-specific explanations from exact published revisions and approved evidence without permitting AI to change canonical answers, publication state, learner score, or mastery.

## Required software

- immutable grounding bundles containing revision, answer evidence, concept, and source references;
- structured explanation layers: correction, selected-distractor analysis, concept refresher, shortcut, and related practice;
- model routing, cache keys, prompt/model versioning, cost ceilings, retries, and explicit unavailable state;
- validation of claimed answer, evidence references, required layers, and provider output shape;
- disagreement/review queue for contradictions or unsupported claims;
- immutable explanation revisions and approval state;
- visible output limited to approved explanations or explicit unavailable responses;
- provider-outage fallback that leaves core practice operational;
- Phase 5 evaluator and inherited regression suite.

## Non-goals

- changing official/canonical answers;
- auto-publishing unreviewed output;
- allowing AI to write score, mastery, rights, or publication fields;
- fabricating expert approval or production provider credentials.

## Acceptance tests

Correct grounded output can be approved; answer contradictions and unsupported references enter review; distractor analysis is mandatory; provider outage yields unavailable; cache keys are deterministic and version-sensitive; cost ceilings block expensive work; only approved/unavailable output is learner-visible; canonical truth is unchanged; and all inherited workflows remain green.
