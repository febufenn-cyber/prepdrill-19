-- Phase 10 immutable billing events and derived entitlements.
create schema if not exists billing_ops;
create table if not exists billing_ops.plans (
  plan_id text not null,
  version integer not null,
  payload jsonb not null,
  active boolean not null,
  primary key(plan_id,version)
);
create table if not exists billing_ops.provider_events (
  event_id text primary key,
  mode text not null,
  subscription_id text not null,
  learner_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null,
  event_version bigint not null,
  occurred_at timestamptz not null,
  payload_hash text not null,
  payload jsonb not null
);
create table if not exists billing_ops.subscriptions (
  subscription_id text primary key,
  learner_id uuid not null references auth.users(id) on delete cascade,
  plan_id text,
  status text not null,
  access_until timestamptz,
  source_version bigint not null,
  last_event_id text not null references billing_ops.provider_events(event_id)
);
create table if not exists billing_ops.entitlement_events (
  entitlement_event_id text primary key,
  subscription_id text not null references billing_ops.subscriptions(subscription_id),
  status text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
create table if not exists billing_ops.mode_activation (
  mode text primary key,
  active boolean not null,
  owner_id uuid references auth.users(id),
  owner_label text not null,
  reason text not null,
  activated_at timestamptz not null default now()
);
alter table billing_ops.plans enable row level security;
alter table billing_ops.provider_events enable row level security;
alter table billing_ops.subscriptions enable row level security;
alter table billing_ops.entitlement_events enable row level security;
alter table billing_ops.mode_activation enable row level security;
create policy "learners read own subscriptions" on billing_ops.subscriptions for select to authenticated using (learner_id=auth.uid());
revoke insert, update, delete on all tables in schema billing_ops from anon, authenticated;
