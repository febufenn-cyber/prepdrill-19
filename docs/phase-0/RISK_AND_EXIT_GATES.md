# Risk Register and Exit Gates

## Critical risks

| Risk | Severity | Detection | Mitigation/decision |
|---|---:|---|---|
| Wrong questions/answers destroy trust | Critical | 250-item audit + golden set | Block uncertain content |
| Unclear rights/provenance | Critical | per-question source review | withhold until resolved |
| Targeted drills feel no better than random | Critical | blinded relevance test | revise learner model/value proposition |
| Core loop communicates only a score | Critical | usability test | redesign result/recommendation |
| AI conflicts with canonical truth | High | explanation evaluation | canonical-first review queue |
| Taxonomy too broad/narrow | High | map 250 questions | consolidate/split controlled concepts |
| Guest merge loses progress | High | architecture + later integration tests | stable anonymous ID + idempotent merge |
| Free substitutes fully satisfy the need | High | behavioural interviews | narrow/alter value proposition |
| Acquisition relies on spam | High | controlled smoke tests | partnership/content-led channels |
| Recommendations become repetitive | Medium | manual simulations | diversity and repeat constraints |

Each active risk must have an owner, status, evidence link and next decision date.

## Weighted exit score

| Dimension | Weight |
|---|---:|
| User pain and segment evidence | 20 |
| Core-loop/adaptive value | 20 |
| Content readiness | 20 |
| Trust/provenance viability | 10 |
| Learning-model clarity | 10 |
| Distribution evidence | 10 |
| Technical feasibility | 5 |
| Payment signal | 5 |

## Advance rule

Proceed to Phase 1 only when:

- total score ≥ 75/100;
- content readiness ≥ 15/20;
- core-loop value ≥ 15/20;
- no critical risk is open;
- first user and content scope are explicit;
- Phase 1 acceptance tests are approved.

## Hard stops

Do not begin broad production work if:

- answer/source uncertainty is widespread;
- rights cannot be classified;
- learners cannot perceive targeted relevance;
- one error is being presented as stable weakness;
- taxonomy mapping is inconsistent;
- no credible initial user channel exists;
- the promise remains merely “many questions with AI.”

## Exit review template

For each dimension record:

- score and scorer;
- evidence links;
- strongest contrary evidence;
- unresolved uncertainty;
- decision: proceed, narrow, repeat experiment, pivot segment, or stop.

No score may override an unresolved critical risk.
