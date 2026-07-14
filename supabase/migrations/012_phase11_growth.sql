-- Phase 11 public growth attribution, referrals, and experiments.
create schema if not exists growth_ops;
create table if not exists growth_ops.attribution (
  subject_type text not null,
  subject_id text not null,
  first_campaign text not null,
  last_campaign text not null,
  first_at timestamptz not null,
  last_at timestamptz not null,
  primary key(subject_type,subject_id)
);
create table if not exists growth_ops.conversions (
  conversion_id text primary key,
  account_id uuid not null references auth.users(id) on delete cascade,
  conversion_type text not null,
  campaign text not null,
  created_at timestamptz not null default now(),
  unique(account_id,conversion_type)
);
create table if not exists growth_ops.referrals (
  code text primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  owner_device_hash text not null,
  max_redemptions integer not null,
  redeemed_count integer not null default 0,
  active boolean not null default true
);
create table if not exists growth_ops.redemptions (
  redemption_id text primary key,
  code text not null references growth_ops.referrals(code),
  redeemer_id uuid not null references auth.users(id) on delete cascade unique,
  device_hash text not null unique,
  created_at timestamptz not null default now()
);
create table if not exists growth_ops.experiments (
  experiment_id text primary key,
  hypothesis text not null,
  primary_metric text not null,
  guardrails jsonb not null,
  variants jsonb not null,
  allocation integer not null,
  active boolean not null,
  killed boolean not null default false
);
alter table growth_ops.attribution enable row level security;
alter table growth_ops.conversions enable row level security;
alter table growth_ops.referrals enable row level security;
alter table growth_ops.redemptions enable row level security;
alter table growth_ops.experiments enable row level security;
create policy "users read own conversions" on growth_ops.conversions for select to authenticated using (account_id=auth.uid());
create policy "users read own referrals" on growth_ops.referrals for select to authenticated using (owner_id=auth.uid());
revoke insert, update, delete on all tables in schema growth_ops from anon, authenticated;
