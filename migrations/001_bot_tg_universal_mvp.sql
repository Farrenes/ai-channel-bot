-- BotTG universal MVP schema
-- Apply this migration with your PostgreSQL migration runner.

BEGIN;

CREATE TABLE IF NOT EXISTS topic_profiles (
    id SERIAL PRIMARY KEY,
    topic_config_id INT UNIQUE REFERENCES topic_configs(id) ON DELETE CASCADE,
    raw_topic TEXT NOT NULL,
    normalized_topic TEXT NOT NULL,
    topic_type TEXT NOT NULL,
    domain TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'blocked')),
    content_strategy TEXT NOT NULL,
    default_post_format TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ru',
    tone TEXT NOT NULL DEFAULT 'practical',
    depth TEXT NOT NULL DEFAULT 'medium',
    allowed_source_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    blocked_source_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    requires_human_approval BOOLEAN NOT NULL DEFAULT FALSE,
    topic_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_sources (
    id SERIAL PRIMARY KEY,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE SET NULL,
    url TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL,
    source_category TEXT NOT NULL DEFAULT 'general',
    source_trust_level TEXT NOT NULL DEFAULT 'unknown',
    supported_level TEXT NOT NULL CHECK (supported_level IN ('supported', 'partially_supported', 'unsupported', 'suspicious', 'high_risk', 'blocked')),
    parser_strategy TEXT NOT NULL DEFAULT 'html',
    content_license_risk TEXT NOT NULL DEFAULT 'unknown',
    requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    access_mode TEXT NOT NULL CHECK (access_mode IN ('rss', 'api', 'html', 'telegram', 'forum', 'document', 'unknown')) DEFAULT 'unknown',
    verification_status TEXT NOT NULL CHECK (verification_status IN ('new', 'checking', 'verified', 'verified_low_confidence', 'needs_user_confirmation', 'unsupported_access', 'irrelevant', 'low_authority', 'blocked', 'failed', 'disabled')) DEFAULT 'new',
    authority_score INT NOT NULL DEFAULT 0,
    relevance_score INT NOT NULL DEFAULT 0,
    freshness_score INT NOT NULL DEFAULT 0,
    risk_score INT NOT NULL DEFAULT 0,
    last_checked_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_error TEXT DEFAULT '',
    is_user_added BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_sources_topic_config_id ON content_sources(topic_config_id);
CREATE INDEX IF NOT EXISTS idx_content_sources_domain ON content_sources(domain);
CREATE INDEX IF NOT EXISTS idx_content_sources_status ON content_sources(verification_status, supported_level, is_active);

CREATE TABLE IF NOT EXISTS source_validation_runs (
    id SERIAL PRIMARY KEY,
    source_id INT NOT NULL REFERENCES content_sources(id) ON DELETE CASCADE,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('new', 'checking', 'verified', 'verified_low_confidence', 'needs_user_confirmation', 'unsupported_access', 'irrelevant', 'low_authority', 'blocked', 'failed', 'disabled')),
    http_status INT,
    detected_access_mode TEXT NOT NULL DEFAULT 'unknown',
    detected_source_type TEXT NOT NULL DEFAULT 'unknown',
    relevance_score INT NOT NULL DEFAULT 0,
    authority_score INT NOT NULL DEFAULT 0,
    freshness_score INT NOT NULL DEFAULT 0,
    risk_score INT NOT NULL DEFAULT 0,
    requires_user_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
    summary TEXT NOT NULL DEFAULT '',
    raw_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    checked_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_validation_runs_source_id ON source_validation_runs(source_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_validation_runs_topic_config_id ON source_validation_runs(topic_config_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS source_fetch_runs (
    id SERIAL PRIMARY KEY,
    workflow_run_id TEXT NOT NULL,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE SET NULL,
    source_id INT NOT NULL REFERENCES content_sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'success', 'partial_success', 'failed', 'skipped', 'rate_limited')),
    items_found INT NOT NULL DEFAULT 0,
    items_inserted INT NOT NULL DEFAULT 0,
    items_duplicate INT NOT NULL DEFAULT 0,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    error_message TEXT NOT NULL DEFAULT '',
    cost_units INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_topic_config_id ON source_fetch_runs(topic_config_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_source_id ON source_fetch_runs(source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_workflow_run_id ON source_fetch_runs(workflow_run_id);

CREATE TABLE IF NOT EXISTS content_candidates (
    id SERIAL PRIMARY KEY,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE SET NULL,
    source_id INT NOT NULL REFERENCES content_sources(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL DEFAULT '',
    published_at_source TIMESTAMP,
    detected_topic TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'ru',
    content_hash TEXT NOT NULL,
    relevance_score INT NOT NULL DEFAULT 0,
    quality_score INT NOT NULL DEFAULT 0,
    novelty_score INT NOT NULL DEFAULT 0,
    authority_score INT NOT NULL DEFAULT 0,
    risk_score INT NOT NULL DEFAULT 0,
    virality_score INT NOT NULL DEFAULT 0,
    evergreen_score INT NOT NULL DEFAULT 0,
    commercial_score INT NOT NULL DEFAULT 0,
    final_score INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('new', 'deduplicating', 'duplicate', 'scoring', 'accepted', 'rejected_low_relevance', 'rejected_low_quality', 'rejected_safety', 'rejected_stale', 'queued_for_generation', 'used', 'archived')) DEFAULT 'new',
    reject_reason TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_content_candidates_topic_config_id ON content_candidates(topic_config_id, status, final_score DESC);
CREATE INDEX IF NOT EXISTS idx_content_candidates_source_id ON content_candidates(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_candidates_url ON content_candidates(url);
CREATE INDEX IF NOT EXISTS idx_content_candidates_status ON content_candidates(status, final_score DESC);

CREATE TABLE IF NOT EXISTS generated_posts (
    id SERIAL PRIMARY KEY,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE SET NULL,
    candidate_id INT REFERENCES content_candidates(id) ON DELETE SET NULL,
    idea_id INT REFERENCES ideas_pool(id) ON DELETE SET NULL,
    prompt_id INT REFERENCES topic_prompts(id) ON DELETE SET NULL,
    style_profile_id INT,
    title TEXT NOT NULL DEFAULT '',
    post_text TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'telegram_html',
    version INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('drafting', 'draft', 'reviewing', 'needs_rewrite', 'rewritten', 'approved', 'scheduled', 'publishing', 'published', 'failed_generation', 'failed_validation', 'failed_publish', 'cancelled', 'archived')) DEFAULT 'drafting',
    quality_score INT NOT NULL DEFAULT 0,
    style_match_score INT NOT NULL DEFAULT 0,
    safety_score INT NOT NULL DEFAULT 0,
    fact_check_score INT NOT NULL DEFAULT 0,
    tokens_input INT NOT NULL DEFAULT 0,
    tokens_output INT NOT NULL DEFAULT 0,
    generation_cost NUMERIC(12, 4) NOT NULL DEFAULT 0,
    scheduled_for TIMESTAMP,
    published_post_id INT REFERENCES published_posts(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL DEFAULT '',
    failure_reason TEXT NOT NULL DEFAULT '',
    review_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_generated_posts_idempotency_key
    ON generated_posts(idempotency_key)
    WHERE idempotency_key <> '';

CREATE INDEX IF NOT EXISTS idx_generated_posts_topic_config_id ON generated_posts(topic_config_id, status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_generated_posts_candidate_id ON generated_posts(candidate_id);
CREATE INDEX IF NOT EXISTS idx_generated_posts_published_post_id ON generated_posts(published_post_id);

CREATE TABLE IF NOT EXISTS usage_counters (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE CASCADE,
    plan_code TEXT NOT NULL,
    period_type TEXT NOT NULL CHECK (period_type IN ('day', 'month')),
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    posts_published INT NOT NULL DEFAULT 0,
    source_checks INT NOT NULL DEFAULT 0,
    fetch_runs INT NOT NULL DEFAULT 0,
    candidates_created INT NOT NULL DEFAULT 0,
    generations INT NOT NULL DEFAULT 0,
    rewrites INT NOT NULL DEFAULT 0,
    tokens_input INT NOT NULL DEFAULT 0,
    tokens_output INT NOT NULL DEFAULT 0,
    llm_cost NUMERIC(12, 4) NOT NULL DEFAULT 0,
    crawl_cost_units INT NOT NULL DEFAULT 0,
    style_learning_runs INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, topic_config_id, period_type, period_start)
);

CREATE INDEX IF NOT EXISTS idx_usage_counters_topic_config_id ON usage_counters(topic_config_id, period_type, period_start);
CREATE INDEX IF NOT EXISTS idx_usage_counters_user_id ON usage_counters(user_id, period_type, period_start);

CREATE TABLE IF NOT EXISTS event_log (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    workflow_run_id TEXT NOT NULL DEFAULT '',
    user_id BIGINT,
    topic_config_id INT REFERENCES topic_configs(id) ON DELETE SET NULL,
    source_id INT REFERENCES content_sources(id) ON DELETE SET NULL,
    candidate_id INT REFERENCES content_candidates(id) ON DELETE SET NULL,
    generated_post_id INT REFERENCES generated_posts(id) ON DELETE SET NULL,
    published_post_id INT REFERENCES published_posts(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    score_before INT,
    score_after INT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_log_event_type ON event_log(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_workflow_run_id ON event_log(workflow_run_id);
CREATE INDEX IF NOT EXISTS idx_event_log_topic_config_id ON event_log(topic_config_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_source_id ON event_log(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_candidate_id ON event_log(candidate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_generated_post_id ON event_log(generated_post_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_published_post_id ON event_log(published_post_id, created_at DESC);

-- Compatibility updates for existing tables.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'raw_topic'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN raw_topic TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'normalized_topic'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN normalized_topic TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'topic_type'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN topic_type TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'domain'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN domain TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'risk_level'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN risk_level TEXT DEFAULT 'medium';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'content_strategy'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN content_strategy TEXT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'default_post_format'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN default_post_format TEXT DEFAULT 'telegram_short';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'language'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN language TEXT DEFAULT 'ru';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'tone'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN tone TEXT DEFAULT 'practical';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'depth'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN depth TEXT DEFAULT 'medium';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'allowed_source_types'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN allowed_source_types JSONB DEFAULT '[]'::jsonb;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'blocked_source_types'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN blocked_source_types JSONB DEFAULT '[]'::jsonb;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'topic_configs' AND column_name = 'requires_human_approval'
    ) THEN
        ALTER TABLE topic_configs ADD COLUMN requires_human_approval BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'idempotency_key'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN idempotency_key TEXT DEFAULT '';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'generated_post_id'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN generated_post_id INT;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'telegram_message_id'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN telegram_message_id TEXT DEFAULT '';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'published_posts' AND column_name = 'published_status'
    ) THEN
        ALTER TABLE published_posts ADD COLUMN published_status TEXT DEFAULT 'published';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_published_posts_idempotency_key
    ON published_posts(idempotency_key)
    WHERE idempotency_key <> '';

CREATE UNIQUE INDEX IF NOT EXISTS uq_published_posts_generated_post_id
    ON published_posts(generated_post_id)
    WHERE generated_post_id IS NOT NULL;

COMMIT;
