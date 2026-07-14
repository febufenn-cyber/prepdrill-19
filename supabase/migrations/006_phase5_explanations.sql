-- Phase 5 grounded explanation revisions and review queue.
create schema if not exists explanation_ops;
create table if not exists explanation_ops.grounding_bundles (
  bundle_id text primary key,
  fingerprint text not null unique,
  published_revision_id text not null,
  correct_option_id text not null,
  concept_id text not null,
  evidence jsonb not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
create table if not exists explanation_ops.generation_requests (
  request_id text primary key,
  cache_key text not null unique,
  bundle_id text not null references explanation_ops.grounding_bundles(bundle_id),
  selected_option_id text not null,
  model text not null,
  prompt_version text not null,
  estimated_cost_micros bigint not null,
  status text not null,
  created_at timestamptz not null default now()
);
create table if not exists explanation_ops.explanation_revisions (
  explanation_id text primary key,
  request_id text not null references explanation_ops.generation_requests(request_id),
  revision_number integer not null,
  status text not null,
  content jsonb,
  blockers jsonb not null,
  reviewer_id uuid references auth.users(id),
  reviewer_label text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(request_id, revision_number)
);
create table if not exists explanation_ops.review_queue (
  review_item_id text primary key,
  explanation_id text not null references explanation_ops.explanation_revisions(explanation_id),
  reason text not null,
  status text not null,
  created_at timestamptz not null default now()
);

alter table explanation_ops.grounding_bundles enable row level security;
alter table explanation_ops.generation_requests enable row level security;
alter table explanation_ops.explanation_revisions enable row level security;
alter table explanation_ops.review_queue enable row level security;
revoke all on schema explanation_ops from anon, authenticated;

-- Learner-facing APIs expose only an approved projection or explicit unavailable response.
