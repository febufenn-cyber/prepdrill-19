-- Phase 8 operational controls and audited kill switches.
create schema if not exists platform_ops;
create table if not exists platform_ops.replay_keys (
  scope text not null,
  actor_id text not null,
  idempotency_key text not null,
  payload_hash text not null,
  created_at timestamptz not null default now(),
  primary key(scope,actor_id,idempotency_key)
);
create table if not exists platform_ops.rate_events (
  scope text not null,
  actor_id text not null,
  event_at timestamptz not null default now()
);
create table if not exists platform_ops.feature_switches (
  name text primary key,
  enabled boolean not null,
  safe_default boolean not null,
  updated_by uuid references auth.users(id),
  updated_by_label text not null,
  reason text not null,
  updated_at timestamptz not null default now()
);
create table if not exists platform_ops.feature_switch_events (
  event_id text primary key,
  name text not null,
  enabled boolean not null,
  actor_id uuid references auth.users(id),
  actor_label text not null,
  reason text not null,
  created_at timestamptz not null default now()
);
create table if not exists platform_ops.reliability_evaluations (
  evaluation_id text primary key,
  service text not null,
  metrics jsonb not null,
  passed boolean not null,
  evaluated_at timestamptz not null default now()
);
create table if not exists platform_ops.backup_rehearsals (
  rehearsal_id text primary key,
  source_checksum text not null,
  restored_checksum text not null,
  passed boolean not null,
  evidence jsonb not null,
  performed_at timestamptz not null default now()
);
alter table platform_ops.replay_keys enable row level security;
alter table platform_ops.rate_events enable row level security;
alter table platform_ops.feature_switches enable row level security;
alter table platform_ops.feature_switch_events enable row level security;
alter table platform_ops.reliability_evaluations enable row level security;
alter table platform_ops.backup_rehearsals enable row level security;
revoke all on schema platform_ops from anon, authenticated;
