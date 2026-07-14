-- Phase 14 subject-pack platform and cross-client state contracts.
create schema if not exists platform_expansion;
create table if not exists platform_expansion.subject_packs (
  pack_id text primary key,
  namespace text not null unique,
  payload jsonb not null,
  approved_for_launch boolean not null,
  created_at timestamptz not null default now()
);
create table if not exists platform_expansion.authorizations (
  authorization_id text primary key,
  pack_id text not null references platform_expansion.subject_packs(pack_id),
  corpus_fingerprint text not null,
  gate_passed boolean not null,
  owner_id uuid references auth.users(id),
  owner_label text not null,
  reason text not null,
  active boolean not null,
  created_at timestamptz not null default now(),
  unique(pack_id,corpus_fingerprint)
);
create table if not exists platform_expansion.identity_links (
  guest_id text primary key,
  auth_user_id uuid not null references auth.users(id),
  onboarding_name text not null,
  account_name text not null,
  merge_key text not null unique,
  created_at timestamptz not null default now()
);
create table if not exists platform_expansion.client_states (
  state_id text primary key,
  namespace text not null,
  account_id uuid not null references auth.users(id) on delete cascade,
  platform text not null,
  state_fingerprint text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique(namespace,account_id,platform,state_fingerprint)
);
create table if not exists platform_expansion.expansion_decisions (
  decision_id text primary key,
  target_namespace text not null,
  outcome text not null check(outcome in ('kill','hold','scale')),
  inputs jsonb not null,
  reasons jsonb not null,
  created_at timestamptz not null default now()
);
alter table platform_expansion.subject_packs enable row level security;
alter table platform_expansion.authorizations enable row level security;
alter table platform_expansion.identity_links enable row level security;
alter table platform_expansion.client_states enable row level security;
alter table platform_expansion.expansion_decisions enable row level security;
create policy "users read own client states" on platform_expansion.client_states for select to authenticated using (account_id=auth.uid());
create policy "users read own identity link" on platform_expansion.identity_links for select to authenticated using (auth_user_id=auth.uid());
revoke insert, update, delete on all tables in schema platform_expansion from anon, authenticated;
