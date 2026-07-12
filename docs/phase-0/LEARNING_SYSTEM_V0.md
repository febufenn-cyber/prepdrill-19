# Learning System V0

## Ontology

`exam → paper → unit → topic → concept → optional misconception`

Each question has exactly one primary concept and at most three secondary concepts. Tags use controlled identifiers, not arbitrary free text.

Example:

`ugc_net → paper_1 → research_aptitude → research_methods → experimental_research → confuses_independent_and_dependent_variables`

## Attempt evidence

Append-only attempt events should capture:

- selected answer and correctness;
- response time and time remaining;
- answer changes;
- hint usage;
- learner confidence when requested;
- question difficulty and concept IDs;
- attempt/session sequence;
- timestamp and recommendation origin.

## Mastery output

Store two distinct values:

1. **estimated state**
2. **confidence in that estimate**

Learner-facing states:

- `insufficient_evidence`
- `emerging`
- `likely_weak`
- `improving`
- `stable`
- `strong`
- `due_for_revision`

Do not display false numerical precision during V0.

## Interpretable V0 evidence

The initial model may combine:

- recent accuracy;
- difficulty-adjusted accuracy;
- response-time deviation;
- exposures across separate sessions;
- recency decay;
- consistency on related concepts;
- repeated distractor/misconception evidence.

One error cannot create a high-confidence weakness. The system must be able to explain every recommendation using stored evidence.

## Recommendation contract

Every recommendation returns:

- target concept IDs;
- reason codes and learner-readable explanation;
- desired question count;
- difficulty range;
- diversity constraints;
- review due time;
- fallback when evidence is insufficient.

### Candidate composition

A default daily set may draw from:

- 40% likely weak concepts;
- 20% newly learned/recent concepts;
- 20% spaced revision;
- 10% mixed exam-style coverage;
- 10% challenge/confidence calibration.

These are hypotheses, not permanent constants.

### Constraints

- avoid exact repeats within a configured window;
- rotate topics and question formats;
- avoid serving only the lowest-scored concept;
- balance challenge with achievable questions;
- separate diagnostic questions from training leakage where needed.

## Explanation layers

1. concise correction;
2. why the selected distractor was wrong;
3. concept refresher;
4. optional exam shortcut;
5. targeted follow-up.

Canonical explanations are preferred. AI personalisation is cached, source-grounded and unable to override answer keys. Model/key disagreement creates a review event.
