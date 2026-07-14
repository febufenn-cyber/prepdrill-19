# Phase 13 Build Contract — Controlled Content Scaling and Generated-Question Quarantine

## Goal

Increase practice coverage without contaminating official truth, mocks, mastery, or learner trust by keeping every generated or AI-assisted candidate in a separately evaluated quarantine until explicit human promotion.

## Required software

- immutable lineage from source question, concept, generation request, prompt/model version, and candidate revision;
- quarantine states separated from canonical publication states;
- at least two independent solver claims with answer agreement and evidence;
- structural validation, ambiguity checks, exact/near similarity checks, concept-drift checks, difficulty targeting, and answer consistency;
- cost and latency accounting per generated and approved item;
- human review with named reviewer, reason, and immutable promotion event;
- shadow-only release, complaint tracking, psychometric monitoring, automatic stop rules, retirement, and rollback;
- default exclusion from official archives, full mocks, public previous-year pages, and mastery updates;
- evaluator covering solver disagreement, duplicate leakage, ambiguity, concept drift, difficulty, human promotion, complaint stop rules, and isolation;
- all inherited workflows green.

## Non-goals

- presenting generated content as official previous-year material;
- auto-publishing because two models agree;
- using experimental performance to update production mastery by default;
- hiding lineage or generation cost;
- fabricating human review or real psychometric evidence.

## Acceptance tests

Candidates start quarantined; insufficient or disagreeing solver claims block promotion; duplicate, ambiguous, concept-drifted, invalid-answer, and out-of-range difficulty candidates fail; clean candidates still require a named human reviewer; promoted items retain generated provenance and remain excluded from official mocks/archives/mastery by default; complaint or quality thresholds automatically stop release and retire items; cost-per-approved-item is measurable; and all inherited suites remain green.