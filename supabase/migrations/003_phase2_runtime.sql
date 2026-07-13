-- Phase 2 learner runtime. Learner reads are scoped by auth.uid(); writes are service-owned.

create schema if not exists learning_runtime;

create table if not exists learning_runtime.launch_authorizations (
  authorization_id text primary key,
  evaluation_id text not null unique references content_review.readiness_gate_evaluations(evaluation_id),
  corpus_fingerprint text not null,
  owner_id uuid references auth.users(id),
  owner_label text not null,
  reason text not null,
  active boolean not null default true,
  authorized_at timestamptz not null default now(),
  revoked_at timestamptz
);

create table if not exists learning_runtime.learners (
  learner_id uuid primary key references auth.users(id) on delete cascade,
  timezone text not null default 'UTC',
  created_at timestamptz not null default now()
);

create table if not exists learning_runtime.sessions (
  session_id text primary key,
  learner_id uuid not null references learning_runtime.learners(learner_id) on delete cascade,
  authorization_id text not null references learning_runtime.launch_authorizations(authorization_id),
  mode text not null check (mode in ('adaptive', 'mixed', 'recheck')),
  requested_size integer not null check (requested_size between 1 and 100),
  seed text not null,
  status text not null check (status in ('active', 'completed', 'abandoned')),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  correct_count integer not null default 0 check (correct_count >= 0),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  item_count integer not null default 0 check (item_count >= 0)
);

create table if not exists learning_runtime.session_items (
  session_id text not null references learning_runtime.sessions(session_id) on delete cascade,
  ordinal integer not null check (ordinal >= 0),
  published_question_id text not null references content_public.published_questions(published_question_id),
  question_id text not null references content_core.canonical_questions(question_id),
  revision_id text not null references content_core.question_revisions(revision_id),
  unit_id text not null,
  concept_id text not null,
  question_type text not null,
  selection_reason text not null,
  payload_hash text not null,
  primary key (session_id, ordinal),
  unique (session_id, published_question_id)
);

create table if not exists learning_runtime.attempts (
  attempt_id text primary key,
  idempotency_key text not null unique,
  session_id text not null references learning_runtime.sessions(session_id) on delete cascade,
  ordinal integer not null,
  learner_id uuid not null references learning_runtime.learners(learner_id) on delete cascade,
  published_question_id text not null references content_public.published_questions(published_question_id),
  selected_option_id text,
  correct_option_id text not null,
  outcome text not null check (outcome in ('correct', 'incorrect', 'skipped', 'timeout')),
  response_ms integer not null default 0 check (response_ms >= 0),
  payload_hash text not null,
  submitted_at timestamptz not null default now(),
  unique (session_id, ordinal)
);

create table if not exists learning_runtime.concept_mastery (
  learner_id uuid not null references learning_runtime.learners(learner_id) on delete cascade,
  concept_id text not null,
  attempts integer not null check (attempts >= 0),
  correct integer not null check (correct >= 0),
  incorrect integer not null check (incorrect >= 0),
  skipped integer not null check (skipped >= 0),
  mastery_score numeric(8,7) not null check (mastery_score between 0 and 1),
  uncertainty numeric(8,7) not null check (uncertainty between 0 and 1),
  last_attempt_at timestamptz not null,
  next_review_at timestamptz not null,
  primary key (learner_id, concept_id)
);

create table if not exists learning_runtime.recheck_queue (
  learner_id uuid not null references learning_runtime.learners(learner_id) on delete cascade,
  published_question_id text not null references content_public.published_questions(published_question_id),
  source_attempt_id text not null references learning_runtime.attempts(attempt_id),
  due_at timestamptz not null,
  priority integer not null,
  reason text not null,
  status text not null check (status in ('pending', 'completed', 'cancelled')),
  updated_at timestamptz not null default now(),
  primary key (learner_id, published_question_id)
);

create table if not exists learning_runtime.explanations (
  explanation_id text primary key,
  attempt_id text not null unique references learning_runtime.attempts(attempt_id) on delete cascade,
  status text not null check (status in ('grounded', 'unavailable')),
  explanation_json jsonb not null,
  grounding_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists learning_runtime.daily_activity (
  learner_id uuid not null references learning_runtime.learners(learner_id) on delete cascade,
  activity_date date not null,
  attempts integer not null default 0 check (attempts >= 0),
  correct integer not null default 0 check (correct >= 0),
  completed_sessions integer not null default 0 check (completed_sessions >= 0),
  primary key (learner_id, activity_date)
);

create table if not exists learning_runtime.events (
  event_id text primary key,
  learner_id uuid references learning_runtime.learners(learner_id) on delete cascade,
  session_id text references learning_runtime.sessions(session_id) on delete cascade,
  event_type text not null,
  payload_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists learning_runtime.evaluations (
  evaluation_id text primary key,
  evaluator_version text not null,
  passed boolean not null,
  report_json jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_runtime_attempts_learner
  on learning_runtime.attempts(learner_id, submitted_at desc);
create index if not exists idx_runtime_mastery_weak
  on learning_runtime.concept_mastery(learner_id, mastery_score, next_review_at);
create index if not exists idx_runtime_recheck_due
  on learning_runtime.recheck_queue(learner_id, status, due_at, priority desc);

alter table learning_runtime.launch_authorizations enable row level security;
alter table learning_runtime.learners enable row level security;
alter table learning_runtime.sessions enable row level security;
alter table learning_runtime.session_items enable row level security;
alter table learning_runtime.attempts enable row level security;
alter table learning_runtime.concept_mastery enable row level security;
alter table learning_runtime.recheck_queue enable row level security;
alter table learning_runtime.explanations enable row level security;
alter table learning_runtime.daily_activity enable row level security;
alter table learning_runtime.events enable row level security;
alter table learning_runtime.evaluations enable row level security;

-- Learners may read only their own derived runtime state. All writes are service-owned.
create policy "learners read own profile"
on learning_runtime.learners for select to authenticated
using (learner_id = auth.uid());

create policy "learners read own sessions"
on learning_runtime.sessions for select to authenticated
using (learner_id = auth.uid());

create policy "learners read own session items"
on learning_runtime.session_items for select to authenticated
using (exists (
  select 1 from learning_runtime.sessions s
  where s.session_id = session_items.session_id and s.learner_id = auth.uid()
));

create policy "learners read own attempts"
on learning_runtime.attempts for select to authenticated
using (learner_id = auth.uid());

create policy "learners read own mastery"
on learning_runtime.concept_mastery for select to authenticated
using (learner_id = auth.uid());

create policy "learners read own rechecks"
on learning_runtime.recheck_queue for select to authenticated
using (learner_id = auth.uid());

create policy "learners read own explanations"
on learning_runtime.explanations for select to authenticated
using (exists (
  select 1 from learning_runtime.attempts a
  where a.attempt_id = explanations.attempt_id and a.learner_id = auth.uid()
));

create policy "learners read own activity"
on learning_runtime.daily_activity for select to authenticated
using (learner_id = auth.uid());

revoke all on learning_runtime.launch_authorizations from anon, authenticated;
revoke insert, update, delete on learning_runtime.learners from anon, authenticated;
revoke insert, update, delete on learning_runtime.sessions from anon, authenticated;
revoke insert, update, delete on learning_runtime.session_items from anon, authenticated;
revoke insert, update, delete on learning_runtime.attempts from anon, authenticated;
revoke insert, update, delete on learning_runtime.concept_mastery from anon, authenticated;
revoke insert, update, delete on learning_runtime.recheck_queue from anon, authenticated;
revoke insert, update, delete on learning_runtime.explanations from anon, authenticated;
revoke insert, update, delete on learning_runtime.daily_activity from anon, authenticated;
revoke all on learning_runtime.events from anon, authenticated;
revoke all on learning_runtime.evaluations from anon, authenticated;

grant usage on schema learning_runtime to authenticated;
grant select on learning_runtime.learners to authenticated;
grant select on learning_runtime.sessions to authenticated;
grant select on learning_runtime.session_items to authenticated;
grant select on learning_runtime.attempts to authenticated;
grant select on learning_runtime.concept_mastery to authenticated;
grant select on learning_runtime.recheck_queue to authenticated;
grant select on learning_runtime.explanations to authenticated;
grant select on learning_runtime.daily_activity to authenticated;
