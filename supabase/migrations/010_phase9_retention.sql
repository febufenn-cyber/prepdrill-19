-- Phase 9 consented communication and learning-continuity projections.
create schema if not exists retention_ops;
create table if not exists retention_ops.preferences (
  learner_id uuid not null references auth.users(id) on delete cascade,
  channel text not null,
  consented boolean not null,
  timezone_name text not null,
  quiet_start time not null,
  quiet_end time not null,
  daily_limit integer not null,
  updated_at timestamptz not null default now(),
  primary key(learner_id,channel)
);
create table if not exists retention_ops.message_decisions (
  decision_id text primary key,
  learner_id uuid not null references auth.users(id) on delete cascade,
  channel text not null,
  category text not null,
  idempotency_key text not null unique,
  allowed boolean not null,
  reason text not null,
  action_type text not null,
  action_id text not null,
  decided_at timestamptz not null default now()
);
create table if not exists retention_ops.outbound_queue (
  message_id text primary key,
  decision_id text not null references retention_ops.message_decisions(decision_id),
  body text not null,
  status text not null,
  provider_reference text,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create table if not exists retention_ops.weekly_reports (
  report_id text primary key,
  learner_id uuid not null references auth.users(id) on delete cascade,
  week_start date not null,
  source_fingerprint text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique(learner_id,week_start,source_fingerprint)
);
alter table retention_ops.preferences enable row level security;
alter table retention_ops.message_decisions enable row level security;
alter table retention_ops.outbound_queue enable row level security;
alter table retention_ops.weekly_reports enable row level security;
create policy "learners read own preferences" on retention_ops.preferences for select to authenticated using (learner_id=auth.uid());
create policy "learners read own decisions" on retention_ops.message_decisions for select to authenticated using (learner_id=auth.uid());
create policy "learners read own reports" on retention_ops.weekly_reports for select to authenticated using (learner_id=auth.uid());
revoke insert, update, delete on all tables in schema retention_ops from anon, authenticated;
