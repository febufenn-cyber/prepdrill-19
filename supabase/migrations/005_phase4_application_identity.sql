-- Phase 4 guest-first application identity and progress references.
create schema if not exists application_runtime;

create table if not exists application_runtime.guest_profiles (
  guest_id text primary key,
  device_hash text not null unique,
  onboarding_name text not null,
  merged_user_id uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create table if not exists application_runtime.progress_refs (
  progress_id text primary key,
  owner_user_id uuid references auth.users(id),
  owner_guest_id text references application_runtime.guest_profiles(guest_id),
  reference_type text not null,
  reference_id text not null,
  created_at timestamptz not null default now(),
  check ((owner_user_id is null) <> (owner_guest_id is null))
);
create table if not exists application_runtime.merge_events (
  merge_id text primary key,
  guest_id text not null references application_runtime.guest_profiles(guest_id),
  user_id uuid not null references auth.users(id),
  idempotency_key text not null unique,
  transferred_count integer not null,
  created_at timestamptz not null default now()
);
create table if not exists application_runtime.flow_requests (
  flow_id text primary key,
  user_id uuid references auth.users(id),
  guest_id text references application_runtime.guest_profiles(guest_id),
  mode text not null,
  seed text not null,
  status text not null,
  payload jsonb not null,
  idempotency_key text not null unique,
  created_at timestamptz not null default now()
);

alter table application_runtime.guest_profiles enable row level security;
alter table application_runtime.progress_refs enable row level security;
alter table application_runtime.merge_events enable row level security;
alter table application_runtime.flow_requests enable row level security;

create policy "users read own progress refs" on application_runtime.progress_refs
for select to authenticated using (owner_user_id = auth.uid());
create policy "users read own flows" on application_runtime.flow_requests
for select to authenticated using (user_id = auth.uid());

revoke insert, update, delete on all tables in schema application_runtime from anon, authenticated;
