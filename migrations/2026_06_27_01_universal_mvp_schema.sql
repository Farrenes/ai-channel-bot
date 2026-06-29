BEGIN;

-- -------------------------------------------------------------------
-- Enum types
-- -------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'topic_profile_status_enum') THEN
        CREATE TYPE topic_profile_status_enum AS ENUM ('draft', 'active', 'paused', 'archived');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_type_enum') THEN
        CREATE TYPE source_type_enum AS ENUM ('news', 'blog', 'official', 'social', 'forum', 'docs', 'marketplace', 'other');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_access_mode_enum') THEN
        CREATE TYPE source_access_mode_enum AS ENUM ('rss', 'api', 'html');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_verification_status_enum') THEN
        CREATE TYPE source_verification_status_enum AS ENUM (
            'new',
            'checking',
            'verified',
            'verified_low_confidence',
            'needs_user_confirmation',
            'unsupported_access',
            'irrelevant',
            'low_authority',
            'blocked'
        );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'candidate_status_enum') THEN
        CREATE TYPE candidate_status_enum AS ENUM (
            'new',
            'queued',
            'scored',
            'selected',
            'rejected',
            'ready_for_generation',
            'generated',
            'archived'
        );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'generated_post_status_enum') THEN
        CREATE TYPE generated_post_status_enum AS ENUM (
            'draft',
            'reviewing',
            'approved',
            'scheduled',
            'published',
            'rejected',
            'failed',
            'archived'
        );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_level_enum') THEN
        CREATE TYPE event_level_enum AS ENUM ('debug', 'info', 'warning', 'error');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'usage_period_enum') THEN
        CREATE TYPE usage_period_enum AS ENUM ('day', 'week', 'month');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflow_run_status_enum') THEN
        CREATE TYPE workflow_run_status_enum AS ENUM ('queued', 'running', 'succeeded', 'failed', 'skipped', 'cancelled');
    END IF;
END
$$;

-- -------------------------------------------------------------------
-- Canonical topic profile
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS topic_profiles (
    id SERIAL PRIMARY KEY,
    topic_name TEXT NOT NULL UNIQUE,
    display_name TEXT,
    summary TEXT,
    status topic_profile_status_enum NOT NULL DEFAULT 'draft',
    language_code TEXT NOT NULL DEFAULT 'ru',
    tone TEXT,
    content_format TEXT NOT NULL DEFAULT 'telegram_html',
    strategy TEXT,
    risk_level SMALLINT NOT NULL DEFAULT 0 CHECK (risk_level BETWEEN 0 AND 100),
    approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    blocked_keywords TEXT[] NOT NULL DEFAULT '{}',
    allowed_source_types source_type_enum[] NOT NULL DEFAULT '{}',
    blocked_source_types source_type_enum[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------
-- Legacy compatible tables
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ideas_pool (
    id SERIAL PRIMARY KEY,
    title TEXT,
    source TEXT,
    link TEXT,
    category TEXT,
    score_b2c INT,
    score_utility INT,
    score_savability INT,
    score_repostability INT,
    score_practical INT,
    total_score INT,
    raw_description TEXT,
    status TEXT DEFAULT 'pending',
    topic_profile_id INT,
    topic_config_id INT,
    source_id INT,
    candidate_id INT,
    generated_post_id INT,
    content_hash TEXT,
    publish_idempotency_key TEXT,
    published_post_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS published_posts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    post_text TEXT NOT NULL,
    source_info TEXT,
    category TEXT,
    topic_profile_id INT,
    topic_config_id INT,
    source_id INT,
    candidate_id INT,
    generated_post_id INT,
    publish_idempotency_key TEXT,
    telegram_message_id TEXT,
    content_hash TEXT,
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_style_examples (
    id SERIAL PRIMARY KEY,
    post_text TEXT NOT NULL,
    post_url TEXT,
    category TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS channel_style_profile (
    id SERIAL PRIMARY KEY,
    avg_paragraph_length INT DEFAULT 50,
    avg_post_length INT DEFAULT 500,
    tone TEXT DEFAULT 'экспертный',
    opening_style TEXT DEFAULT 'с факта',
    favorite_words TEXT[] DEFAULT '{}',
    structure_pattern TEXT DEFAULT 'ДО/ПОСЛЕ',
    emoji_frequency TEXT DEFAULT 'умеренно',
    raw_profile TEXT DEFAULT '',
    topic_profile_id INT,
    topic_config_id INT,
    source_id INT,
    generated_post_id INT,
    profile_version INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS post_feedback (
    id SERIAL PRIMARY KEY,
    post_id INT,
    reaction TEXT CHECK (reaction IN ('like', 'dislike', 'neutral')),
    topic_profile_id INT,
    topic_config_id INT,
    generated_post_id INT,
    source_id INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topic_configs (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    target_channel TEXT,
    sources JSONB DEFAULT '[]'::jsonb,
    keywords TEXT[] DEFAULT '{}',
    categories JSONB DEFAULT '{}'::jsonb,
    prompt_id INT,
    topic_profile_id INT,
    canonical_slug TEXT,
    profile_status topic_profile_status_enum DEFAULT 'draft',
    last_profiled_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topic_prompts (
    id SERIAL PRIMARY KEY,
    topic_name TEXT NOT NULL,
    final_prompt TEXT NOT NULL,
    step_architect TEXT,
    step_constraints TEXT,
    step_cot TEXT,
    step_editor TEXT,
    tokens_input INT DEFAULT 0,
    tokens_output INT DEFAULT 0,
    version INT DEFAULT 1,
    topic_config_id INT,
    prompt_scope TEXT DEFAULT 'topic',
    prompt_hash TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- -------------------------------------------------------------------
-- Canonical source and candidate tables
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS content_sources (
    id SERIAL PRIMARY KEY,
    topic_profile_id INT NOT NULL,
    topic_config_id INT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    topic TEXT,
    source_type source_type_enum NOT NULL DEFAULT 'other',
    access_mode source_access_mode_enum NOT NULL DEFAULT 'html',
    verification_status source_verification_status_enum NOT NULL DEFAULT 'new',
    authority SMALLINT NOT NULL DEFAULT 0 CHECK (authority BETWEEN 0 AND 100),
    language_code TEXT NOT NULL DEFAULT 'ru',
    is_user_added BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority SMALLINT NOT NULL DEFAULT 100,
    rss_url TEXT,
    last_checked_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_content_sources_normalized_url UNIQUE (normalized_url)
);

CREATE TABLE IF NOT EXISTS source_validation_runs (
    id SERIAL PRIMARY KEY,
    source_id INT NOT NULL,
    topic_profile_id INT,
    topic_config_id INT,
    run_status workflow_run_status_enum NOT NULL DEFAULT 'queued',
    result_status source_verification_status_enum,
    request_source TEXT DEFAULT 'api',
    idempotency_key TEXT,
    checked_url TEXT,
    fetch_mode source_access_mode_enum,
    http_status INT,
    authority SMALLINT CHECK (authority BETWEEN 0 AND 100),
    error_message TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_fetch_runs (
    id SERIAL PRIMARY KEY,
    source_id INT NOT NULL,
    topic_profile_id INT,
    topic_config_id INT,
    validation_run_id INT,
    run_status workflow_run_status_enum NOT NULL DEFAULT 'queued',
    idempotency_key TEXT,
    fetch_mode source_access_mode_enum,
    http_status INT,
    items_seen INT NOT NULL DEFAULT 0 CHECK (items_seen >= 0),
    items_saved INT NOT NULL DEFAULT 0 CHECK (items_saved >= 0),
    content_hash TEXT,
    error_message TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS content_candidates (
    id SERIAL PRIMARY KEY,
    topic_profile_id INT NOT NULL,
    topic_config_id INT,
    source_id INT,
    external_id TEXT,
    url TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    raw_text TEXT,
    published_at_source TIMESTAMP,
    content_hash TEXT NOT NULL,
    relevance_score SMALLINT NOT NULL DEFAULT 0 CHECK (relevance_score BETWEEN 0 AND 100),
    quality_score SMALLINT NOT NULL DEFAULT 0 CHECK (quality_score BETWEEN 0 AND 100),
    novelty_score SMALLINT NOT NULL DEFAULT 0 CHECK (novelty_score BETWEEN 0 AND 100),
    candidate_status candidate_status_enum NOT NULL DEFAULT 'new',
    selection_reason TEXT,
    rejection_reason TEXT,
    selected_at TIMESTAMP,
    scored_at TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_content_candidates_content_hash UNIQUE (content_hash)
);

-- -------------------------------------------------------------------
-- Counters and generated posts
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS usage_counters (
    id SERIAL PRIMARY KEY,
    topic_profile_id INT NOT NULL,
    topic_config_id INT,
    counter_date DATE NOT NULL,
    period usage_period_enum NOT NULL DEFAULT 'day',
    posts_published INT NOT NULL DEFAULT 0 CHECK (posts_published >= 0),
    source_checks INT NOT NULL DEFAULT 0 CHECK (source_checks >= 0),
    fetch_runs INT NOT NULL DEFAULT 0 CHECK (fetch_runs >= 0),
    active_sources INT NOT NULL DEFAULT 0 CHECK (active_sources >= 0),
    candidates_created INT NOT NULL DEFAULT 0 CHECK (candidates_created >= 0),
    generations INT NOT NULL DEFAULT 0 CHECK (generations >= 0),
    rewrites INT NOT NULL DEFAULT 0 CHECK (rewrites >= 0),
    tokens_input INT NOT NULL DEFAULT 0 CHECK (tokens_input >= 0),
    tokens_output INT NOT NULL DEFAULT 0 CHECK (tokens_output >= 0),
    llm_cost NUMERIC(12,4) NOT NULL DEFAULT 0,
    crawl_cost_units NUMERIC(12,4) NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ux_usage_counters_topic_period UNIQUE (topic_profile_id, counter_date, period)
);

CREATE TABLE IF NOT EXISTS generated_posts (
    id SERIAL PRIMARY KEY,
    topic_profile_id INT NOT NULL,
    topic_config_id INT,
    candidate_id INT,
    idea_id INT,
    source_id INT,
    prompt_id INT,
    style_profile_id INT,
    title TEXT NOT NULL,
    post_text TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'telegram_html',
    version INT NOT NULL DEFAULT 1,
    status generated_post_status_enum NOT NULL DEFAULT 'draft',
    quality_score SMALLINT CHECK (quality_score BETWEEN 0 AND 100),
    style_match_score SMALLINT CHECK (style_match_score BETWEEN 0 AND 100),
    safety_score SMALLINT CHECK (safety_score BETWEEN 0 AND 100),
    fact_check_score SMALLINT CHECK (fact_check_score BETWEEN 0 AND 100),
    tokens_input INT NOT NULL DEFAULT 0 CHECK (tokens_input >= 0),
    tokens_output INT NOT NULL DEFAULT 0 CHECK (tokens_output >= 0),
    generation_cost NUMERIC(12,4) NOT NULL DEFAULT 0,
    scheduled_for TIMESTAMP,
    published_at TIMESTAMP,
    published_post_id INT,
    publish_idempotency_key TEXT,
    telegram_message_id TEXT,
    failure_reason TEXT,
    review_notes TEXT,
    reviewed_at TIMESTAMP,
    approved_at TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------
-- Event log
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS event_log (
    id BIGSERIAL PRIMARY KEY,
    topic_profile_id INT,
    topic_config_id INT,
    source_id INT,
    candidate_id INT,
    generated_post_id INT,
    published_post_id INT,
    event_type TEXT NOT NULL,
    event_level event_level_enum NOT NULL DEFAULT 'info',
    correlation_key TEXT,
    idempotency_key TEXT,
    message TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------
-- Compatibility and idempotency columns for existing tables
-- -------------------------------------------------------------------

ALTER TABLE ideas_pool
    ADD COLUMN IF NOT EXISTS topic_profile_id INT,
    ADD COLUMN IF NOT EXISTS topic_config_id INT,
    ADD COLUMN IF NOT EXISTS source_id INT,
    ADD COLUMN IF NOT EXISTS candidate_id INT,
    ADD COLUMN IF NOT EXISTS generated_post_id INT,
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS publish_idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS published_post_id INT;

ALTER TABLE published_posts
    ADD COLUMN IF NOT EXISTS topic_profile_id INT,
    ADD COLUMN IF NOT EXISTS topic_config_id INT,
    ADD COLUMN IF NOT EXISTS source_id INT,
    ADD COLUMN IF NOT EXISTS candidate_id INT,
    ADD COLUMN IF NOT EXISTS generated_post_id INT,
    ADD COLUMN IF NOT EXISTS publish_idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS telegram_message_id TEXT,
    ADD COLUMN IF NOT EXISTS content_hash TEXT;

ALTER TABLE channel_style_profile
    ADD COLUMN IF NOT EXISTS topic_profile_id INT,
    ADD COLUMN IF NOT EXISTS topic_config_id INT,
    ADD COLUMN IF NOT EXISTS source_id INT,
    ADD COLUMN IF NOT EXISTS generated_post_id INT,
    ADD COLUMN IF NOT EXISTS profile_version INT NOT NULL DEFAULT 1;

ALTER TABLE post_feedback
    ADD COLUMN IF NOT EXISTS topic_profile_id INT,
    ADD COLUMN IF NOT EXISTS topic_config_id INT,
    ADD COLUMN IF NOT EXISTS generated_post_id INT,
    ADD COLUMN IF NOT EXISTS source_id INT;

ALTER TABLE topic_configs
    ADD COLUMN IF NOT EXISTS topic_profile_id INT,
    ADD COLUMN IF NOT EXISTS canonical_slug TEXT,
    ADD COLUMN IF NOT EXISTS profile_status topic_profile_status_enum DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS last_profiled_at TIMESTAMP;

ALTER TABLE topic_prompts
    ADD COLUMN IF NOT EXISTS topic_config_id INT,
    ADD COLUMN IF NOT EXISTS prompt_scope TEXT DEFAULT 'topic',
    ADD COLUMN IF NOT EXISTS prompt_hash TEXT;

-- -------------------------------------------------------------------
-- Foreign keys that need both sides to exist
-- -------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ideas_pool_topic_profile') THEN
        ALTER TABLE ideas_pool
            ADD CONSTRAINT fk_ideas_pool_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ideas_pool_topic_config') THEN
        ALTER TABLE ideas_pool
            ADD CONSTRAINT fk_ideas_pool_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ideas_pool_source') THEN
        ALTER TABLE ideas_pool
            ADD CONSTRAINT fk_ideas_pool_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ideas_pool_candidate') THEN
        ALTER TABLE ideas_pool
            ADD CONSTRAINT fk_ideas_pool_candidate
            FOREIGN KEY (candidate_id) REFERENCES content_candidates(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ideas_pool_generated_post') THEN
        ALTER TABLE ideas_pool
            ADD CONSTRAINT fk_ideas_pool_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_ideas_pool_published_post') THEN
        ALTER TABLE ideas_pool
            ADD CONSTRAINT fk_ideas_pool_published_post
            FOREIGN KEY (published_post_id) REFERENCES published_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_published_posts_topic_profile') THEN
        ALTER TABLE published_posts
            ADD CONSTRAINT fk_published_posts_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_published_posts_topic_config') THEN
        ALTER TABLE published_posts
            ADD CONSTRAINT fk_published_posts_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_published_posts_source') THEN
        ALTER TABLE published_posts
            ADD CONSTRAINT fk_published_posts_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_published_posts_candidate') THEN
        ALTER TABLE published_posts
            ADD CONSTRAINT fk_published_posts_candidate
            FOREIGN KEY (candidate_id) REFERENCES content_candidates(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_published_posts_generated_post') THEN
        ALTER TABLE published_posts
            ADD CONSTRAINT fk_published_posts_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_channel_style_profile_topic_profile') THEN
        ALTER TABLE channel_style_profile
            ADD CONSTRAINT fk_channel_style_profile_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_channel_style_profile_topic_config') THEN
        ALTER TABLE channel_style_profile
            ADD CONSTRAINT fk_channel_style_profile_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_channel_style_profile_source') THEN
        ALTER TABLE channel_style_profile
            ADD CONSTRAINT fk_channel_style_profile_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_channel_style_profile_generated_post') THEN
        ALTER TABLE channel_style_profile
            ADD CONSTRAINT fk_channel_style_profile_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_feedback_post') THEN
        ALTER TABLE post_feedback
            ADD CONSTRAINT fk_post_feedback_post
            FOREIGN KEY (post_id) REFERENCES published_posts(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_feedback_topic_profile') THEN
        ALTER TABLE post_feedback
            ADD CONSTRAINT fk_post_feedback_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_feedback_topic_config') THEN
        ALTER TABLE post_feedback
            ADD CONSTRAINT fk_post_feedback_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_feedback_generated_post') THEN
        ALTER TABLE post_feedback
            ADD CONSTRAINT fk_post_feedback_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_feedback_source') THEN
        ALTER TABLE post_feedback
            ADD CONSTRAINT fk_post_feedback_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_topic_configs_topic_profile') THEN
        ALTER TABLE topic_configs
            ADD CONSTRAINT fk_topic_configs_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_topic_prompts_topic_config') THEN
        ALTER TABLE topic_prompts
            ADD CONSTRAINT fk_topic_prompts_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE CASCADE;
    END IF;
END
$$;

-- -------------------------------------------------------------------
-- Compatibility links for canonical tables
-- -------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_sources_topic_profile') THEN
        ALTER TABLE content_sources
            ADD CONSTRAINT fk_content_sources_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_sources_topic_config') THEN
        ALTER TABLE content_sources
            ADD CONSTRAINT fk_content_sources_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_validation_runs_source') THEN
        ALTER TABLE source_validation_runs
            ADD CONSTRAINT fk_source_validation_runs_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_validation_runs_topic_profile') THEN
        ALTER TABLE source_validation_runs
            ADD CONSTRAINT fk_source_validation_runs_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_validation_runs_topic_config') THEN
        ALTER TABLE source_validation_runs
            ADD CONSTRAINT fk_source_validation_runs_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_fetch_runs_source') THEN
        ALTER TABLE source_fetch_runs
            ADD CONSTRAINT fk_source_fetch_runs_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_fetch_runs_topic_profile') THEN
        ALTER TABLE source_fetch_runs
            ADD CONSTRAINT fk_source_fetch_runs_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_fetch_runs_topic_config') THEN
        ALTER TABLE source_fetch_runs
            ADD CONSTRAINT fk_source_fetch_runs_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_source_fetch_runs_validation_run') THEN
        ALTER TABLE source_fetch_runs
            ADD CONSTRAINT fk_source_fetch_runs_validation_run
            FOREIGN KEY (validation_run_id) REFERENCES source_validation_runs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_candidates_topic_profile') THEN
        ALTER TABLE content_candidates
            ADD CONSTRAINT fk_content_candidates_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_candidates_topic_config') THEN
        ALTER TABLE content_candidates
            ADD CONSTRAINT fk_content_candidates_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_candidates_source') THEN
        ALTER TABLE content_candidates
            ADD CONSTRAINT fk_content_candidates_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_usage_counters_topic_profile') THEN
        ALTER TABLE usage_counters
            ADD CONSTRAINT fk_usage_counters_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_usage_counters_topic_config') THEN
        ALTER TABLE usage_counters
            ADD CONSTRAINT fk_usage_counters_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_topic_profile') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_topic_config') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_candidate') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_candidate
            FOREIGN KEY (candidate_id) REFERENCES content_candidates(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_idea') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_idea
            FOREIGN KEY (idea_id) REFERENCES ideas_pool(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_source') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_prompt') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_prompt
            FOREIGN KEY (prompt_id) REFERENCES topic_prompts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_style_profile') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_style_profile
            FOREIGN KEY (style_profile_id) REFERENCES channel_style_profile(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_generated_posts_published_post') THEN
        ALTER TABLE generated_posts
            ADD CONSTRAINT fk_generated_posts_published_post
            FOREIGN KEY (published_post_id) REFERENCES published_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_log_topic_profile') THEN
        ALTER TABLE event_log
            ADD CONSTRAINT fk_event_log_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_log_topic_config') THEN
        ALTER TABLE event_log
            ADD CONSTRAINT fk_event_log_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_log_source') THEN
        ALTER TABLE event_log
            ADD CONSTRAINT fk_event_log_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_log_candidate') THEN
        ALTER TABLE event_log
            ADD CONSTRAINT fk_event_log_candidate
            FOREIGN KEY (candidate_id) REFERENCES content_candidates(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_log_generated_post') THEN
        ALTER TABLE event_log
            ADD CONSTRAINT fk_event_log_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_event_log_published_post') THEN
        ALTER TABLE event_log
            ADD CONSTRAINT fk_event_log_published_post
            FOREIGN KEY (published_post_id) REFERENCES published_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

-- -------------------------------------------------------------------
-- Indexes
-- -------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_topic_profiles_status ON topic_profiles(status);
CREATE INDEX IF NOT EXISTS idx_topic_profiles_updated_at ON topic_profiles(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas_pool(status);
CREATE INDEX IF NOT EXISTS idx_ideas_score ON ideas_pool(total_score);
CREATE INDEX IF NOT EXISTS idx_ideas_topic_profile ON ideas_pool(topic_profile_id);
CREATE INDEX IF NOT EXISTS idx_ideas_topic_config ON ideas_pool(topic_config_id);
CREATE INDEX IF NOT EXISTS idx_ideas_candidate ON ideas_pool(candidate_id);
CREATE INDEX IF NOT EXISTS idx_ideas_generated_post ON ideas_pool(generated_post_id);
CREATE INDEX IF NOT EXISTS idx_ideas_content_hash ON ideas_pool(content_hash);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ideas_publish_idempotency_key
    ON ideas_pool(publish_idempotency_key)
    WHERE publish_idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_published_at ON published_posts(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_published_category ON published_posts(category);
CREATE INDEX IF NOT EXISTS idx_published_topic_profile_published_at
    ON published_posts(topic_profile_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_published_topic_config_published_at
    ON published_posts(topic_config_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_published_generated_post ON published_posts(generated_post_id);
CREATE INDEX IF NOT EXISTS idx_published_candidate ON published_posts(candidate_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_published_posts_publish_idempotency_key
    ON published_posts(publish_idempotency_key)
    WHERE publish_idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_published_posts_generated_post_id
    ON published_posts(generated_post_id)
    WHERE generated_post_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_style_examples_cat ON channel_style_examples(category);
CREATE INDEX IF NOT EXISTS idx_channel_style_profile_topic_profile ON channel_style_profile(topic_profile_id);
CREATE INDEX IF NOT EXISTS idx_channel_style_profile_topic_config ON channel_style_profile(topic_config_id);

CREATE INDEX IF NOT EXISTS idx_feedback_post ON post_feedback(post_id);
CREATE INDEX IF NOT EXISTS idx_post_feedback_topic_profile ON post_feedback(topic_profile_id);
CREATE INDEX IF NOT EXISTS idx_post_feedback_topic_config ON post_feedback(topic_config_id);
CREATE INDEX IF NOT EXISTS idx_post_feedback_generated_post ON post_feedback(generated_post_id);

CREATE INDEX IF NOT EXISTS idx_topic_name ON topic_configs(name);
CREATE INDEX IF NOT EXISTS idx_topic_configs_topic_profile ON topic_configs(topic_profile_id);
CREATE INDEX IF NOT EXISTS idx_topic_configs_profile_status ON topic_configs(profile_status);

CREATE INDEX IF NOT EXISTS idx_prompt_topic ON topic_prompts(topic_name);
CREATE INDEX IF NOT EXISTS idx_topic_prompts_topic_config ON topic_prompts(topic_config_id);
CREATE INDEX IF NOT EXISTS idx_topic_prompts_version ON topic_prompts(topic_name, version DESC);

CREATE INDEX IF NOT EXISTS idx_sources_topic_priority
    ON content_sources(topic_profile_id, is_active, priority DESC);
CREATE INDEX IF NOT EXISTS idx_sources_topic_config ON content_sources(topic_config_id);
CREATE INDEX IF NOT EXISTS idx_sources_verification_status ON content_sources(verification_status);

CREATE INDEX IF NOT EXISTS idx_source_validation_runs_source_created
    ON source_validation_runs(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_validation_runs_topic_created
    ON source_validation_runs(topic_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_validation_runs_status_created
    ON source_validation_runs(run_status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_source_validation_runs_idempotency_key
    ON source_validation_runs(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_source_created
    ON source_fetch_runs(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_validation_created
    ON source_fetch_runs(validation_run_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_topic_created
    ON source_fetch_runs(topic_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_fetch_runs_status_created
    ON source_fetch_runs(run_status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_source_fetch_runs_idempotency_key
    ON source_fetch_runs(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_candidates_queue
    ON content_candidates(topic_profile_id, candidate_status, relevance_score DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_source ON content_candidates(source_id, published_at_source DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_topic_config ON content_candidates(topic_config_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_candidates_source_external
    ON content_candidates(source_id, external_id)
    WHERE source_id IS NOT NULL AND external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_usage_counters_topic_period
    ON usage_counters(topic_profile_id, period, counter_date DESC);
CREATE INDEX IF NOT EXISTS idx_usage_counters_topic_config ON usage_counters(topic_config_id);

CREATE INDEX IF NOT EXISTS idx_generated_posts_topic_status_schedule
    ON generated_posts(topic_profile_id, status, scheduled_for DESC);
CREATE INDEX IF NOT EXISTS idx_generated_posts_candidate ON generated_posts(candidate_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_generated_posts_topic_config ON generated_posts(topic_config_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_generated_posts_publish_idempotency_key
    ON generated_posts(publish_idempotency_key)
    WHERE publish_idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_generated_posts_published_post_id
    ON generated_posts(published_post_id)
    WHERE published_post_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_event_log_topic_created ON event_log(topic_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_topic_config_created ON event_log(topic_config_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_source_created ON event_log(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_candidate_created ON event_log(candidate_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_generated_post_created ON event_log(generated_post_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_published_post_created ON event_log(published_post_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_type_created ON event_log(event_type, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_event_log_idempotency_key
    ON event_log(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

COMMIT;
