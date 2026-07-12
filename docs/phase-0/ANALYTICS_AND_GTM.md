# Analytics and GTM Validation

## Metric hierarchy

### Outcome metric

**Weak concepts converted into stable performance states.**

### Leading metrics

- diagnostic completion rate;
- wrong-answer explanation open/helpful rate;
- recommendation acceptance rate;
- targeted-drill completion rate;
- next-day and next-week return;
- repeat-error reduction;
- question-report rate;
- guest-to-account progress merge success.

Do not optimise primarily for time spent.

## Event taxonomy

Minimum events:

- `landing_viewed`
- `diagnostic_started`
- `question_viewed`
- `answer_submitted`
- `answer_changed`
- `explanation_opened`
- `explanation_helpful_marked`
- `question_reported`
- `drill_completed`
- `result_viewed`
- `recommendation_shown`
- `recommendation_started`
- `account_created`
- `guest_progress_merged`
- `weak_concept_improved`
- `next_day_returned`

Question events include stable question/concept IDs, drill type, difficulty, response time, correctness and session sequence. Avoid unnecessary personal data and full question text in third-party analytics.

## Positioning smoke tests

Test at least two messages:

A. **Stop guessing what to study. Take a five-minute UGC NET diagnostic and discover your weakest Paper 1 concepts.**

B. **Improve UGC NET Paper 1 in ten minutes a day with drills targeted from your mistakes.**

## Funnel

`community post/daily question → sample diagnostic → evidence-based result → recommended drill → optional account`

Potential controlled channels:

- permitted UGC NET Telegram communities;
- student/college networks;
- tutor partnerships;
- topic-specific YouTube content leading to a drill;
- searchable previous-year-question explanation pages later.

## Smoke-test evidence

Record:

- impressions where available;
- landing visits;
- diagnostic starts/completions;
- waitlist or account intent;
- segment quality, especially repeaters;
- message variant;
- qualitative reason for conversion/non-conversion.

Do not infer scalable acquisition from one friendly group.

## Payment validation

Do not integrate billing in Phase 0. Test value packages instead:

1. unlimited practice archive;
2. adaptive daily plan and weakness map;
3. improvement system with explanations, mocks and weekly reports.

Past purchases and a small refundable reservation are stronger evidence than hypothetical willingness-to-pay answers.
