# BotTG DB Migration Notes

## What This Migration Adds

### Canonical tables

- `topic_profiles`
- `content_sources`
- `source_validation_runs`
- `source_fetch_runs`
- `content_candidates`
- `generated_posts`
- `usage_counters`
- `event_log`

### Compatibility tables kept in place

- `ideas_pool`
- `published_posts`
- `channel_style_profile`
- `post_feedback`
- `topic_configs`
- `topic_prompts`

## Statuses and enums

- `topic_profile_status_enum`: `draft`, `active`, `paused`, `archived`
- `source_type_enum`: `news`, `blog`, `official`, `social`, `forum`, `docs`, `marketplace`, `other`
- `source_access_mode_enum`: `rss`, `api`, `html`
- `source_verification_status_enum`: `new`, `checking`, `verified`, `verified_low_confidence`, `needs_user_confirmation`, `unsupported_access`, `irrelevant`, `low_authority`, `blocked`
- `workflow_run_status_enum`: `queued`, `running`, `succeeded`, `failed`, `skipped`, `cancelled`
- `candidate_status_enum`: `new`, `queued`, `scored`, `selected`, `rejected`, `ready_for_generation`, `generated`, `archived`
- `generated_post_status_enum`: `draft`, `reviewing`, `approved`, `scheduled`, `published`, `rejected`, `failed`, `archived`
- `event_level_enum`: `debug`, `info`, `warning`, `error`
- `usage_period_enum`: `day`, `week`, `month`

## Workflow indexes

- Topic lookup: `topic_profiles(topic_name)`, `topic_configs(name)`, `topic_configs(topic_profile_id)`
- Source lookup: `content_sources(topic_profile_id, is_active, priority DESC)`, `content_sources(verification_status)`
- Source validation: `source_validation_runs(source_id, created_at DESC)`, `source_validation_runs(run_status, created_at DESC)`
- Source fetch: `source_fetch_runs(source_id, created_at DESC)`, `source_fetch_runs(validation_run_id, created_at DESC)`, `source_fetch_runs(run_status, created_at DESC)`
- Candidate queue: `content_candidates(topic_profile_id, candidate_status, relevance_score DESC, created_at DESC)`
- Generated post queue: `generated_posts(topic_profile_id, status, scheduled_for DESC)`
- Usage counters: `usage_counters(topic_profile_id, period, counter_date DESC)`
- Event log: `event_log(topic_profile_id, created_at DESC)`, `event_log(event_type, created_at DESC)`
- Publish idempotency: `published_posts(publish_idempotency_key)`, `generated_posts(publish_idempotency_key)`, `published_posts(generated_post_id)`

## Compatibility fields

- `ideas_pool`: topic/source/candidate/generated-post linkage plus publish idempotency fields
- `published_posts`: topic/source/candidate/generated-post linkage plus publish idempotency and message id fields
- `channel_style_profile`: topic/profile linkage plus profile version
- `post_feedback`: topic/profile/generated-post/source linkage
- `topic_configs`: topic profile link plus canonical slug and profile status
- `topic_prompts`: topic config link plus prompt scope/hash
- `source_validation_runs` and `source_fetch_runs`: status, idempotency, and source/topic linkage for workflow tracing

## Risks

1. This migration is additive only. It does not backfill old rows into the new canonical tables.
2. Foreign keys on the compatibility columns are nullable, so the schema stays safe for the current code, but the app will need follow-up writes to populate them.
3. The unique idempotency indexes assume new columns start empty or null. If historical manual data already uses those columns after a partial rollout, cleanup may be needed before re-running the migration.
4. `database.py` still creates old tables on startup, so the migration should be applied as the source of truth before any future schema cleanup work.
