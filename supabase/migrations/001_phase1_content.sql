-- Prepdrill Phase 1 truth layer. Internal schemas are intentionally separated
-- from the learner-readable publication schema.
create schema if not exists content_raw;
create schema if not exists content_core;
create schema if not exists content_review;
create schema if not exists content_public;

create table if not exists content_raw.import_batches (
  import_batch_id text primary key,
  adapter_name text not null,
  adapter_version text not null,
  source_document_id text not null,
  source_checksum text not null,
  status text not null check (status in ('running','completed','failed')),
  created_at timestamptz not null default now(),
  unique(adapter_name, adapter_version, source_document_id, source_checksum)
);

create table if not exists content_raw.raw_question_records (
  raw_record_id text primary key,
  import_batch_id text not null references content_raw.import_batches(import_batch_id),
  source_locator text not null,
  raw_payload jsonb not null,
  raw_checksum text not null,
  created_at timestamptz not null default now(),
  unique(import_batch_id, source_locator, raw_checksum)
);

create table if not exists content_core.canonical_questions (
  question_id text primary key,
  created_at timestamptz not null default now()
);

create table if not exists content_core.question_revisions (
  revision_id text primary key,
  question_id text not null references content_core.canonical_questions(question_id),
  version integer not null check (version >= 1),
  content_payload jsonb not null,
  semantic_hash text not null,
  exact_fingerprint text not null,
  near_fingerprint text not null,
  supersedes_revision_id text references content_core.question_revisions(revision_id),
  created_at timestamptz not null default now(),
  unique(question_id, version),
  unique(question_id, semantic_hash)
);

create table if not exists content_core.source_documents (
  source_document_id text primary key,
  title text not null,
  checksum text,
  source_uri text,
  rights_status text not null,
  attribution_requirements text,
  created_at timestamptz not null default now()
);

create table if not exists content_core.question_source_links (
  source_link_id text primary key,
  revision_id text not null references content_core.question_revisions(revision_id),
  source_document_id text not null references content_core.source_documents(source_document_id),
  source_locator text not null,
  provenance_payload jsonb not null,
  created_at timestamptz not null default now(),
  unique(revision_id, source_document_id, source_locator)
);

create table if not exists content_core.answer_claims (
  answer_claim_id text primary key,
  revision_id text not null references content_core.question_revisions(revision_id),
  claimed_option_id text not null,
  evidence_type text not null,
  evidence_reference text,
  claim_status text not null,
  created_at timestamptz not null default now()
);

create table if not exists content_core.assets (
  asset_id text primary key,
  checksum text not null,
  media_type text not null,
  storage_ref text not null,
  verification_status text not null,
  created_at timestamptz not null default now()
);

create table if not exists content_core.shared_contexts (
  context_id text primary key,
  content_payload jsonb not null,
  content_hash text not null,
  verification_status text not null,
  created_at timestamptz not null default now()
);

create table if not exists content_review.validation_runs (
  validation_run_id text primary key,
  revision_id text not null references content_core.question_revisions(revision_id),
  publication_mode boolean not null,
  passed boolean not null,
  created_at timestamptz not null default now()
);

create table if not exists content_review.validation_findings (
  finding_id text primary key,
  validation_run_id text not null references content_review.validation_runs(validation_run_id),
  level text not null,
  code text not null,
  path text not null default '',
  message text not null
);

create table if not exists content_review.review_events (
  review_event_id text primary key,
  revision_id text not null references content_core.question_revisions(revision_id),
  actor_id uuid references auth.users(id),
  actor_label text not null,
  action text not null,
  reason text not null,
  before_payload jsonb,
  after_payload jsonb,
  created_at timestamptz not null default now()
);

create table if not exists content_review.duplicate_candidates (
  candidate_id text primary key,
  left_revision_id text not null references content_core.question_revisions(revision_id),
  right_revision_id text not null references content_core.question_revisions(revision_id),
  duplicate_type text not null,
  confidence numeric(5,4) not null,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  unique(left_revision_id, right_revision_id, duplicate_type)
);

create table if not exists content_public.published_questions (
  published_question_id text primary key,
  question_id text not null references content_core.canonical_questions(question_id),
  revision_id text not null unique references content_core.question_revisions(revision_id),
  payload jsonb not null,
  payload_hash text not null,
  published_at timestamptz not null default now(),
  retired_at timestamptz
);

alter table content_raw.import_batches enable row level security;
alter table content_raw.raw_question_records enable row level security;
alter table content_core.canonical_questions enable row level security;
alter table content_core.question_revisions enable row level security;
alter table content_core.source_documents enable row level security;
alter table content_core.question_source_links enable row level security;
alter table content_core.answer_claims enable row level security;
alter table content_core.assets enable row level security;
alter table content_core.shared_contexts enable row level security;
alter table content_review.validation_runs enable row level security;
alter table content_review.validation_findings enable row level security;
alter table content_review.review_events enable row level security;
alter table content_review.duplicate_candidates enable row level security;
alter table content_public.published_questions enable row level security;

-- No public policies are created for internal schemas. Service-role operations only.
create policy "published questions are publicly readable"
on content_public.published_questions for select
to anon, authenticated
using (retired_at is null);

revoke all on schema content_raw from anon, authenticated;
revoke all on schema content_core from anon, authenticated;
revoke all on schema content_review from anon, authenticated;
grant usage on schema content_public to anon, authenticated;
grant select on content_public.published_questions to anon, authenticated;
