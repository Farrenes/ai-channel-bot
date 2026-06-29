-- Billing, subscriptions, payments, webhooks, limits.
-- Non-destructive migration for the existing asyncpg/SQL migration style.

CREATE TABLE IF NOT EXISTS billing_plans (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_rub NUMERIC(12, 2) NOT NULL CHECK (price_rub >= 0),
    period_days INT NOT NULL CHECK (period_days > 0),
    post_limit INT NOT NULL CHECK (post_limit >= 0),
    source_limit INT NOT NULL CHECK (source_limit >= 0),
    channel_limit INT NOT NULL CHECK (channel_limit >= 0),
    llm_limit INT NOT NULL DEFAULT 0 CHECK (llm_limit >= 0),
    rewrite_limit INT NOT NULL DEFAULT 0 CHECK (rewrite_limit >= 0),
    source_check_limit INT NOT NULL DEFAULT 0 CHECK (source_check_limit >= 0),
    candidate_limit INT NOT NULL DEFAULT 0 CHECK (candidate_limit >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS billing_customers (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    provider TEXT NOT NULL DEFAULT 'internal',
    provider_customer_id TEXT,
    email TEXT,
    phone TEXT,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    ban_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    plan_id BIGINT NOT NULL REFERENCES billing_plans(id),
    provider TEXT NOT NULL DEFAULT 'manual',
    provider_subscription_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_period_end TIMESTAMPTZ NOT NULL,
    trial_ends_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_user_status
    ON billing_subscriptions(user_id, status, current_period_end DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_provider_subscription
    ON billing_subscriptions(provider, provider_subscription_id)
    WHERE provider_subscription_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS billing_payments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    subscription_id BIGINT REFERENCES billing_subscriptions(id),
    plan_id BIGINT NOT NULL REFERENCES billing_plans(id),
    provider TEXT NOT NULL,
    provider_payment_id TEXT,
    amount_rub NUMERIC(12, 2) NOT NULL CHECK (amount_rub >= 0),
    currency TEXT NOT NULL DEFAULT 'RUB',
    status TEXT NOT NULL DEFAULT 'pending',
    confirmation_url TEXT,
    idempotency_key TEXT NOT NULL,
    paid_at TIMESTAMPTZ,
    failed_reason TEXT,
    raw_provider_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_provider_payment
    ON billing_payments(provider, provider_payment_id)
    WHERE provider_payment_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_payment_idempotency
    ON billing_payments(provider, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_billing_payments_user_status
    ON billing_payments(user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS billing_invoices (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    payment_id BIGINT NOT NULL REFERENCES billing_payments(id),
    provider_invoice_id TEXT,
    receipt_status TEXT NOT NULL DEFAULT 'not_created',
    fiscal_receipt_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS billing_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    processing_status TEXT NOT NULL DEFAULT 'received',
    processed_at TIMESTAMPTZ,
    error_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, event_id)
);

CREATE INDEX IF NOT EXISTS idx_billing_webhook_events_status
    ON billing_webhook_events(provider, processing_status, created_at DESC);

CREATE TABLE IF NOT EXISTS billing_subscription_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    subscription_id BIGINT REFERENCES billing_subscriptions(id),
    event_type TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT,
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS billing_promocodes (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    discount_percent INT NOT NULL DEFAULT 0 CHECK (discount_percent >= 0 AND discount_percent <= 100),
    extra_days INT NOT NULL DEFAULT 0 CHECK (extra_days >= 0),
    max_uses INT NOT NULL DEFAULT 0 CHECK (max_uses >= 0),
    used_count INT NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    valid_until TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS billing_promocode_uses (
    id BIGSERIAL PRIMARY KEY,
    promocode_id BIGINT NOT NULL REFERENCES billing_promocodes(id),
    user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (promocode_id, user_id)
);

CREATE TABLE IF NOT EXISTS billing_manual_overrides (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    admin_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_manual_overrides_user_action
    ON billing_manual_overrides(user_id, action, expires_at DESC);

CREATE TABLE IF NOT EXISTS billing_usage_counters (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    subscription_id BIGINT REFERENCES billing_subscriptions(id),
    period TEXT NOT NULL DEFAULT 'day',
    counter_date DATE NOT NULL DEFAULT CURRENT_DATE,
    posts_published INT NOT NULL DEFAULT 0,
    source_checks INT NOT NULL DEFAULT 0,
    fetch_runs INT NOT NULL DEFAULT 0,
    scoring_runs INT NOT NULL DEFAULT 0,
    generation_runs INT NOT NULL DEFAULT 0,
    rewrites INT NOT NULL DEFAULT 0,
    llm_tokens INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, period, counter_date)
);

INSERT INTO billing_plans (
    code, name, description, price_rub, period_days,
    post_limit, source_limit, channel_limit, llm_limit,
    rewrite_limit, source_check_limit, candidate_limit, metadata
) VALUES
    (
        'beta', 'Бета', 'Временный ранний доступ для первых пользователей.',
        499, 30, 90, 20, 1, 0, 2, 30, 50,
        '{"posts_per_day_per_channel": 3, "positioning": "temporary_beta"}'::jsonb
    ),
    (
        'base', 'База', 'Основной массовый тариф для одного канала.',
        990, 30, 150, 30, 1, 0, 3, 60, 100,
        '{"posts_per_day_per_channel": 5, "positioning": "main_b2c"}'::jsonb
    ),
    (
        'pro', 'Профи', 'Тариф для активных владельцев каналов.',
        2990, 30, 420, 50, 2, 0, 4, 150, 250,
        '{"posts_per_day_per_channel": 7, "positioning": "active_creators"}'::jsonb
    ),
    (
        'studio', 'Студия', 'Тариф для агентств и многоканальных операций.',
        7990, 30, 1500, 100, 5, 0, 5, 500, 1000,
        '{"posts_per_day_per_channel": 10, "positioning": "agency"}'::jsonb
    )
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price_rub = EXCLUDED.price_rub,
    period_days = EXCLUDED.period_days,
    post_limit = EXCLUDED.post_limit,
    source_limit = EXCLUDED.source_limit,
    channel_limit = EXCLUDED.channel_limit,
    llm_limit = EXCLUDED.llm_limit,
    rewrite_limit = EXCLUDED.rewrite_limit,
    source_check_limit = EXCLUDED.source_check_limit,
    candidate_limit = EXCLUDED.candidate_limit,
    metadata = EXCLUDED.metadata,
    is_active = TRUE,
    updated_at = NOW();
