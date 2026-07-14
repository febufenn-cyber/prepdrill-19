-- Phase 13 generated-content quarantine and shadow release.
create schema if not exists generated_ops;
create table if not exists generated_ops.candidates(candidate_id text primary key,lineage jsonb not null,payload jsonb not null,status text not null,provenance_category text not null,created_at timestamptz not null default now());
create table if not exists generated_ops.solver_claims(candidate_id text not null references generated_ops.candidates(candidate_id),solver_id text not null,answer_id text not null,evidence text not null,independent boolean not null,primary key(candidate_id,solver_id));
create table if not exists generated_ops.evaluations(evaluation_id text primary key,candidate_id text not null references generated_ops.candidates(candidate_id),passed boolean not null,blockers jsonb not null,created_at timestamptz not null default now());
create table if not exists generated_ops.promotions(promotion_id text primary key,candidate_id text not null references generated_ops.candidates(candidate_id),reviewer_id uuid references auth.users(id),reviewer_label text not null,reason text not null,policy jsonb not null,created_at timestamptz not null default now());
create table if not exists generated_ops.shadow_metrics(candidate_id text primary key references generated_ops.candidates(candidate_id),attempts integer not null default 0,correct integer not null default 0,complaints integer not null default 0,active boolean not null default false,retired boolean not null default false);
create table if not exists generated_ops.complaints(complaint_id text primary key,candidate_id text not null references generated_ops.candidates(candidate_id),reason text not null,severity text not null,created_at timestamptz not null default now());
create table if not exists generated_ops.events(event_id text primary key,candidate_id text not null references generated_ops.candidates(candidate_id),event_type text not null,payload jsonb not null,created_at timestamptz not null default now());
alter table generated_ops.candidates enable row level security;
alter table generated_ops.solver_claims enable row level security;
alter table generated_ops.evaluations enable row level security;
alter table generated_ops.promotions enable row level security;
alter table generated_ops.shadow_metrics enable row level security;
alter table generated_ops.complaints enable row level security;
alter table generated_ops.events enable row level security;
revoke all on schema generated_ops from anon, authenticated;
