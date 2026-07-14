-- Phase 7 immutable mock manifests and learner attempt state.
create schema if not exists mock_runtime;
create table if not exists mock_runtime.manifests (
  manifest_id text primary key,
  title text not null,
  duration_seconds integer not null,
  payload jsonb not null,
  manifest_hash text not null unique,
  created_at timestamptz not null default now()
);
create table if not exists mock_runtime.attempts (
  attempt_id text primary key,
  manifest_id text not null references mock_runtime.manifests(manifest_id),
  learner_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null,
  deadline_at timestamptz not null,
  status text not null,
  submitted_at timestamptz,
  result jsonb
);
create table if not exists mock_runtime.responses (
  attempt_id text not null references mock_runtime.attempts(attempt_id),
  ordinal integer not null,
  selected_option_id text,
  marked_for_review boolean not null default false,
  visited boolean not null default false,
  idempotency_key text not null unique,
  updated_at timestamptz not null default now(),
  primary key(attempt_id, ordinal)
);
create table if not exists mock_runtime.events (
  event_id text primary key,
  attempt_id text not null references mock_runtime.attempts(attempt_id),
  event_type text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
alter table mock_runtime.manifests enable row level security;
alter table mock_runtime.attempts enable row level security;
alter table mock_runtime.responses enable row level security;
alter table mock_runtime.events enable row level security;
create policy "learners read own mock attempts" on mock_runtime.attempts for select to authenticated using (learner_id=auth.uid());
create policy "learners read own mock responses" on mock_runtime.responses for select to authenticated using (exists(select 1 from mock_runtime.attempts a where a.attempt_id=responses.attempt_id and a.learner_id=auth.uid()));
revoke insert, update, delete on all tables in schema mock_runtime from anon, authenticated;
