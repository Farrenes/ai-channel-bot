# BotTG Architecture Decisions

## Chosen stack

- Python because the bot, scraping, LLM integration, and API boundaries already live there
- FastAPI because the repo already has clean HTTP contracts and async support
- PostgreSQL because the system is stateful and needs durable idempotency, usage counters, subscriptions, and event logs
- asyncpg because the existing codebase already uses it directly
- aiogram because Telegram runtime is already implemented with it
- n8n as orchestrator only

## Why PostgreSQL

- billing, publish idempotency, event logs, usage counters, and subscriptions need transactional state
- source validation and scoring workflows need traceable persisted runs
- PostgreSQL matches the existing asyncpg codebase and avoids a second data stack

## Why not switch to SQLAlchemy/Alembic now

- the codebase is already built around asyncpg and SQL migrations
- adding a second ORM stack would increase risk and duplication
- the current MVP needs additive migrations, not a rewrite

## Role model

- `ALLOWED_USERS` is the coarse authorization gate
- admin bot and admin billing endpoints are the operator surface
- user-facing API endpoints are separate from admin billing endpoints
- current role handling is simple and static, not a full RBAC system

## Billing design

- `BillingService` is the main entry point
- provider-specific logic is isolated behind `BillingProvider`
- `YooKassa` is the first real provider
- `ManualProvider` handles admin grants and internal operations
- `CloudPayments`, `Robokassa`, and `Telegram Stars` are stubs for later
- webhook deduplication is stored in `billing_webhook_events`
- publish idempotency is stored in `published_posts` and `generated_posts`

## Service layering

- routes validate inputs and return envelopes
- services contain business logic
- repositories hold SQL access
- providers hold external payment vendor integrations

## Topic and content decisions

- raw topic text is converted into a structured `topic_profile`
- scoring is universal, not niche-specific
- generation/review use topic profile fields rather than hardcoded editorial prompts
- review blocks high-risk topics from autopublish

## n8n decision

- n8n is an orchestrator only
- n8n should call HTTP endpoints, not own scoring or policy logic
- n8n should handle scheduling, branching, and error routing

## Publish decision

- Telegram publishing must be idempotent
- duplicate publish attempts should return a deduplicated result instead of sending twice

## Environment decision

- startup uses explicit env validation
- dev-mode billing can be disabled, but that should not silently hide missing config in production

## Open decisions

- Whether `main.py` stays an autonomous polling bot or becomes a thin adapter
- Whether `admin_bot.py` should own more of the admin surface or the FastAPI admin billing routes should become primary
- Whether the legacy schema bootstrap in `database.py` should remain permanently or be retired after migration cleanup
- Whether RouterAI stays the default LLM provider or becomes configurable per workflow
- Whether the billing layer needs full provider webhooks and receipts in MVP or only YooKassa plus manual grants

