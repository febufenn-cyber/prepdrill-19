-- Phase 6 versioned mastery state and immutable daily plans.
create schema if not exists adaptive_learning;
create table if not exists adaptive_learning.mastery_versions (
  model_version text primary key,
  config jsonb not null,
  active boolean not null default false,
  created_at timestamptz not null default now()
);
create table if not exists adaptive_learning.concept_states (
  learner_id uuid not null references auth.users(id) on delete cascade,
  concept_id text not null,
  model_version text not null references adaptive_learning.mastery_versions(model_version),
  score numeric(8,6) not null,
  uncertainty numeric(8,6) not null,
  evidence_count integer not null,
  updated_at timestamptz not null default now(),
  primary key (learner_id, concept_id, model_version)
);
create table if not exists adaptive_learning.daily_plans (
  plan_id text primary key,
  learner_id uuid not null references auth.users(id) on delete cascade,
  plan_date date not null,
  model_version text not null,
  seed text not null,
  items jsonb not null,
  created_at timestamptz not null default now(),
  unique(learner_id, plan_date, model_version, seed)
);
create table if not exists adaptive_learning.shadow_evaluations (
  evaluation_id text primary key,
  production_version text not null,
  shadow_version text not null,
  metrics jsonb not null,
  created_at timestamptz not null default now()
);
alter table adaptive_learning.mastery_versions enable row level security;
alter table adaptive_learning.concept_states enable row level security;
alter table adaptive_learning.daily_plans enable row level security;
alter table adaptive_learning.shadow_evaluations enable row level security;
create policy "learners read own concept states" on adaptive_learning.concept_states for select to authenticated using (learner_id=auth.uid());
create policy "learners read own plans" on adaptive_learning.daily_plans for select to authenticated using (learner_id=auth.uid());
revoke insert, update, delete on all tables in schema adaptive_learning from anon, authenticated;
