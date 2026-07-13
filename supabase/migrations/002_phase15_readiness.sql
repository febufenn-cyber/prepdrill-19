-- Phase 1.5 corpus-readiness evidence. Internal reviewer/service-role access only.

create table if not exists content_review.readiness_audit_runs (
  run_id text primary key,
  name text not null,
  sample_target integer not null check (sample_target > 0),
  seed text not null,
  corpus_fingerprint text not null,
  population_size integer not null check (population_size >= 0),
  status text not null check (status in ('open', 'undersized', 'completed', 'invalidated')),
  criteria_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists content_review.readiness_sample_items (
  run_id text not null references content_review.readiness_audit_runs(run_id),
  revision_id text not null references content_core.question_revisions(revision_id),
  question_id text not null references content_core.canonical_questions(question_id),
  unit_id text not null,
  question_type text not null,
  validation_tier text not null,
  stratum_key text not null,
  ordinal integer not null check (ordinal > 0),
  semantic_hash text not null,
  selected_at timestamptz not null default now(),
  primary key (run_id, revision_id),
  unique (run_id, ordinal)
);

create table if not exists content_review.readiness_reviews (
  review_id text primary key,
  run_id text not null references content_review.readiness_audit_runs(run_id),
  revision_id text not null references content_core.question_revisions(revision_id),
  reviewer_id uuid references auth.users(id),
  reviewer_label text not null,
  verdict text not null check (verdict in ('pass', 'needs_review', 'block', 'retire')),
  rights_ok boolean not null,
  answer_evidence_ok boolean not null,
  render_ok boolean not null,
  mapping_ok boolean not null,
  provenance_ok boolean not null,
  review_seconds integer not null check (review_seconds >= 0),
  notes text not null default '',
  reviewed_at timestamptz not null default now()
);

create table if not exists content_review.readiness_mapping_labels (
  label_id text primary key,
  run_id text not null references content_review.readiness_audit_runs(run_id),
  revision_id text not null references content_core.question_revisions(revision_id),
  reviewer_id uuid references auth.users(id),
  reviewer_label text not null,
  concept_id text not null,
  recorded_at timestamptz not null default now()
);

create table if not exists content_review.readiness_duplicate_adjudications (
  adjudication_id text primary key,
  candidate_id text not null references content_review.duplicate_candidates(candidate_id),
  reviewer_id uuid references auth.users(id),
  reviewer_label text not null,
  decision text not null check (decision in ('same_question', 'distinct_questions', 'retire_left', 'retire_right')),
  canonical_revision_id text references content_core.question_revisions(revision_id),
  reason text not null,
  adjudicated_at timestamptz not null default now()
);

create table if not exists content_review.readiness_gate_evaluations (
  evaluation_id text primary key,
  run_id text not null references content_review.readiness_audit_runs(run_id),
  corpus_fingerprint text not null,
  golden_fingerprint text not null,
  passed boolean not null,
  report_json jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_readiness_reviews_lookup
  on content_review.readiness_reviews(run_id, revision_id, reviewer_label, reviewed_at desc);
create index if not exists idx_readiness_labels_lookup
  on content_review.readiness_mapping_labels(run_id, revision_id, reviewer_label, recorded_at desc);

alter table content_review.readiness_audit_runs enable row level security;
alter table content_review.readiness_sample_items enable row level security;
alter table content_review.readiness_reviews enable row level security;
alter table content_review.readiness_mapping_labels enable row level security;
alter table content_review.readiness_duplicate_adjudications enable row level security;
alter table content_review.readiness_gate_evaluations enable row level security;

-- No anon/authenticated policies are intentionally created. These tables are internal evidence.
revoke all on content_review.readiness_audit_runs from anon, authenticated;
revoke all on content_review.readiness_sample_items from anon, authenticated;
revoke all on content_review.readiness_reviews from anon, authenticated;
revoke all on content_review.readiness_mapping_labels from anon, authenticated;
revoke all on content_review.readiness_duplicate_adjudications from anon, authenticated;
revoke all on content_review.readiness_gate_evaluations from anon, authenticated;
