-- Phase 3 real-corpus activation and reversible migration evidence.
create schema if not exists corpus_activation;

create table if not exists corpus_activation.manifests (
  manifest_id text primary key,
  delivery_name text not null,
  corpus_version text not null,
  manifest_payload jsonb not null,
  manifest_fingerprint text not null unique,
  created_by uuid references auth.users(id),
  created_by_label text not null,
  created_at timestamptz not null default now()
);

create table if not exists corpus_activation.migration_batches (
  batch_id text primary key,
  manifest_id text not null references corpus_activation.manifests(manifest_id),
  status text not null check (status in ('running','completed','rolled_back')),
  created_by uuid references auth.users(id),
  created_by_label text not null,
  created_at timestamptz not null default now(),
  rolled_back_at timestamptz
);

create table if not exists corpus_activation.migration_events (
  event_id text primary key,
  batch_id text not null references corpus_activation.migration_batches(batch_id),
  event_type text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists corpus_activation.evaluations (
  evaluation_id text primary key,
  manifest_id text not null references corpus_activation.manifests(manifest_id),
  corpus_fingerprint text not null,
  passed boolean not null,
  blockers jsonb not null,
  evidence jsonb not null,
  evaluated_at timestamptz not null default now()
);

create table if not exists corpus_activation.authorizations (
  authorization_id text primary key,
  evaluation_id text not null unique references corpus_activation.evaluations(evaluation_id),
  corpus_fingerprint text not null,
  owner_id uuid references auth.users(id),
  owner_label text not null,
  reason text not null,
  active boolean not null default true,
  authorized_at timestamptz not null default now(),
  revoked_at timestamptz
);

alter table corpus_activation.manifests enable row level security;
alter table corpus_activation.migration_batches enable row level security;
alter table corpus_activation.migration_events enable row level security;
alter table corpus_activation.evaluations enable row level security;
alter table corpus_activation.authorizations enable row level security;

-- No anon/authenticated policies: writes and internal evidence reads are service-owned.
revoke all on schema corpus_activation from anon, authenticated;
