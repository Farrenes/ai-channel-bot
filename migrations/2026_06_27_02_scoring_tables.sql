BEGIN;

CREATE TABLE IF NOT EXISTS content_scores (
    id SERIAL PRIMARY KEY,
    topic_profile_id INT,
    topic_config_id INT,
    source_id INT,
    candidate_id INT,
    generated_post_id INT,
    idea_id INT,
    published_post_id INT,
    content_kind TEXT NOT NULL DEFAULT 'candidate' CHECK (content_kind IN ('candidate', 'generated_post', 'published_post')),
    scoring_stage TEXT NOT NULL DEFAULT 'pre_generation' CHECK (scoring_stage IN ('pre_generation', 'post_generation', 'review')),
    content_hash TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    content_text TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    niche TEXT NOT NULL DEFAULT '',
    audience TEXT NOT NULL DEFAULT '',
    format TEXT NOT NULL DEFAULT 'telegram_html',
    post_type TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT 'heuristic',
    score_version INT NOT NULL DEFAULT 1 CHECK (score_version >= 1),
    base_score NUMERIC(6, 2) NOT NULL DEFAULT 0 CHECK (base_score BETWEEN 0 AND 100),
    penalty_score NUMERIC(6, 2) NOT NULL DEFAULT 0 CHECK (penalty_score BETWEEN 0 AND 100),
    total_score NUMERIC(6, 2) NOT NULL DEFAULT 0 CHECK (total_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL DEFAULT 'improve' CHECK (decision IN ('publish', 'improve', 'reject')),
    factor_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    penalty_breakdown JSONB NOT NULL DEFAULT '[]'::jsonb,
    strong_sides JSONB NOT NULL DEFAULT '[]'::jsonb,
    weak_sides JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommended_format TEXT NOT NULL DEFAULT 'telegram_html',
    idempotency_key TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS post_metrics (
    id SERIAL PRIMARY KEY,
    content_score_id INT,
    topic_profile_id INT,
    topic_config_id INT,
    generated_post_id INT,
    published_post_id INT,
    metric_window TEXT NOT NULL DEFAULT 'post_publish' CHECK (metric_window IN ('post_publish', 'day_1', 'day_7', 'day_30')),
    metric_source TEXT NOT NULL DEFAULT 'telegram',
    metric_snapshot_at TIMESTAMP NOT NULL DEFAULT NOW(),
    views_count INT NOT NULL DEFAULT 0 CHECK (views_count >= 0),
    likes_count INT NOT NULL DEFAULT 0 CHECK (likes_count >= 0),
    dislikes_count INT NOT NULL DEFAULT 0 CHECK (dislikes_count >= 0),
    comments_count INT NOT NULL DEFAULT 0 CHECK (comments_count >= 0),
    shares_count INT NOT NULL DEFAULT 0 CHECK (shares_count >= 0),
    saves_count INT NOT NULL DEFAULT 0 CHECK (saves_count >= 0),
    ctr NUMERIC(8, 4) NOT NULL DEFAULT 0 CHECK (ctr >= 0),
    engagement_rate NUMERIC(8, 4) NOT NULL DEFAULT 0 CHECK (engagement_rate >= 0),
    retention_rate NUMERIC(8, 4) NOT NULL DEFAULT 0 CHECK (retention_rate >= 0),
    reaction_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_topic_profile') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_topic_config') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_source') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_source
            FOREIGN KEY (source_id) REFERENCES content_sources(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_candidate') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_candidate
            FOREIGN KEY (candidate_id) REFERENCES content_candidates(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_generated_post') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_idea') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_idea
            FOREIGN KEY (idea_id) REFERENCES ideas_pool(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_content_scores_published_post') THEN
        ALTER TABLE content_scores
            ADD CONSTRAINT fk_content_scores_published_post
            FOREIGN KEY (published_post_id) REFERENCES published_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_metrics_content_score') THEN
        ALTER TABLE post_metrics
            ADD CONSTRAINT fk_post_metrics_content_score
            FOREIGN KEY (content_score_id) REFERENCES content_scores(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_metrics_topic_profile') THEN
        ALTER TABLE post_metrics
            ADD CONSTRAINT fk_post_metrics_topic_profile
            FOREIGN KEY (topic_profile_id) REFERENCES topic_profiles(id) ON DELETE CASCADE;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_metrics_topic_config') THEN
        ALTER TABLE post_metrics
            ADD CONSTRAINT fk_post_metrics_topic_config
            FOREIGN KEY (topic_config_id) REFERENCES topic_configs(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_metrics_generated_post') THEN
        ALTER TABLE post_metrics
            ADD CONSTRAINT fk_post_metrics_generated_post
            FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE SET NULL;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_post_metrics_published_post') THEN
        ALTER TABLE post_metrics
            ADD CONSTRAINT fk_post_metrics_published_post
            FOREIGN KEY (published_post_id) REFERENCES published_posts(id) ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_content_scores_topic_created
    ON content_scores(topic_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_scores_topic_config_created
    ON content_scores(topic_config_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_scores_content_hash
    ON content_scores(content_hash);
CREATE INDEX IF NOT EXISTS idx_content_scores_generated_post
    ON content_scores(generated_post_id);
CREATE INDEX IF NOT EXISTS idx_content_scores_candidate
    ON content_scores(candidate_id);
CREATE INDEX IF NOT EXISTS idx_content_scores_published_post
    ON content_scores(published_post_id);
CREATE INDEX IF NOT EXISTS idx_content_scores_decision_created
    ON content_scores(decision, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_content_scores_idempotency_key
    ON content_scores(idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_content_scores_dedupe
    ON content_scores(topic_profile_id, content_hash, score_version, content_kind)
    WHERE content_hash <> '';

CREATE INDEX IF NOT EXISTS idx_post_metrics_topic_snapshot
    ON post_metrics(topic_profile_id, metric_snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_post_metrics_topic_config_snapshot
    ON post_metrics(topic_config_id, metric_snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_post_metrics_published_post
    ON post_metrics(published_post_id);
CREATE INDEX IF NOT EXISTS idx_post_metrics_generated_post
    ON post_metrics(generated_post_id);
CREATE INDEX IF NOT EXISTS idx_post_metrics_window_snapshot
    ON post_metrics(metric_window, metric_snapshot_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_post_metrics_idempotency_key
    ON post_metrics(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

COMMIT;
