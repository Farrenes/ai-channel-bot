# BotTG Project Handoff

## Product idea

BotTG is a universal Telegram content automation system.
The user provides a free-form topic and source URLs.
The system turns that into a structured `topic_profile`, validates sources, fetches material, scores candidates, generates a Telegram post, reviews it, and publishes with idempotency.

The long-term architecture is:

- `n8n` orchestrates steps
- Python/FastAPI owns business logic
- PostgreSQL stores state
- Telegram is the output channel

## Architecture summary

### Runtime layers

- `main.py` - main content bot runtime and scheduler
- `admin_bot.py` - admin/operator bot
- `api/main.py` - FastAPI gateway for workflow steps
- `scoring_service.py` - separate scoring service on port `8001`
- `database.py` - asyncpg bootstrap and legacy compatibility tables

### Service layer

- `services/topic_profile.py`
- `services/source_validation.py`
- `services/scoring.py`
- `services/generation.py`
- `services/review.py`
- `services/telegram_publish.py`
- `services/billing/*`

### Workflow orchestration

`n8n/workflows/*` contains the workflow templates.
The single-file orchestrator is `n8n/workflows/BotTG-single-file.json`.

## Repository structure

```text
BotTG/
  api/
  app/
  docs/
  migrations/
  n8n/
  outputs/
  scoring/
  services/
  tests/
  main.py
  admin_bot.py
  scoring_service.py
  database.py
  config.py
  llm_generator.py
  parsers.py
  run_*.bat
```

## Key files

- `api/main.py` - includes all routers
- `api/routes/topics.py` - `POST /topics/profile`
- `api/routes/sources.py` - `POST /sources/validate`, `POST /sources/fetch`
- `api/routes/scoring.py` - `POST /score`
- `api/routes/generation.py` - `POST /generation/post`
- `api/routes/review.py` - `POST /review/post`, `POST /review/rewrite`
- `api/routes/telegram.py` - `POST /telegram/publish`
- `api/routes/billing.py` - billing and admin billing endpoints
- `services/billing/service.py` - billing orchestration and guard logic
- `services/billing/repository.py` - SQL access for billing tables
- `services/billing/providers/yookassa.py` - real first provider
- `services/billing/providers/manual.py` - manual admin access provider
- `services/billing/providers/*.py` - provider stubs
- `services/telegram_publish.py` - idempotent publish path
- `services/source_validation.py` - URL inspection and classification
- `services/topic_profile.py` - raw topic -> structured profile
- `services/scoring.py` - universal scoring model and persistence
- `services/generation.py` - prompt-aware generation
- `services/review.py` - approval/rewrite logic
- `database.py` - old schema bootstrap plus compatibility tables
- `migrations/2026_06_28_01_billing.sql` - additive billing migration

## Main user flows

### Topic setup flow

1. User enters raw topic text
2. `POST /topics/profile` returns structured topic profile
3. n8n stores topic metadata and continues

### Source flow

1. User or workflow provides source URL
2. `POST /sources/validate` inspects access mode and authority
3. `POST /sources/fetch` collects candidate items
4. Billing guard runs before expensive steps

### Scoring flow

1. Candidates are filtered
2. `POST /score` computes universal scores
3. Persisted content score rows are written when enabled

### Generation/review flow

1. `POST /generation/post` generates a post from topic profile
2. `POST /review/post` checks safety and autopublish eligibility
3. `POST /review/rewrite` rewrites when needed

### Publish flow

1. `POST /telegram/publish` publishes or mock-publishes
2. Idempotency prevents duplicate publishes
3. Event log records the publish action

### Billing flow

1. `GET /billing/plans`
2. `POST /billing/payments/create`
3. `POST /billing/webhooks/yookassa`
4. `GET /billing/me/subscription`
5. `GET /billing/me/limits`
6. Admin endpoints for grant/ban/reset/cancel

## Database and migrations

### Canonical billing tables

- `billing_plans`
- `billing_customers`
- `billing_subscriptions`
- `billing_payments`
- `billing_invoices`
- `billing_webhook_events`
- `billing_subscription_events`
- `billing_promocodes`
- `billing_promocode_uses`
- `billing_manual_overrides`
- `billing_usage_counters`

### Existing legacy/core tables

- `ideas_pool`
- `published_posts`
- `channel_style_examples`
- `channel_style_profile`
- `post_feedback`
- `topic_configs`
- `topic_prompts`

### Notes

- `database.py` still bootstraps legacy tables on startup
- migrations are additive, not destructive
- billing migration seeds `beta`, `base`, `pro`, `studio`

## API summary

### Topics

- `POST /topics/profile`

### Sources

- `POST /sources/validate`
- `POST /sources/fetch`

### Scoring / generation / review / publish

- `POST /score`
- `POST /generation/post`
- `POST /review/post`
- `POST /review/rewrite`
- `POST /telegram/publish`

### Billing

- `GET /billing/plans`
- `POST /billing/payments/create`
- `GET /billing/payments/{payment_id}/status`
- `POST /billing/webhooks/yookassa`
- `POST /billing/promocode/apply`
- `GET /billing/me/subscription`
- `GET /billing/me/limits`
- `POST /billing/guard`

### Admin billing

- `POST /admin/billing/users/{user_id}/grant-access`
- `POST /admin/billing/users/{user_id}/ban`
- `POST /admin/billing/users/{user_id}/reset-limits`
- `POST /admin/billing/subscriptions/{subscription_id}/cancel`

## Telegram bot flow

### `main.py`

- Runs the main content bot
- Fetches content from scrapers
- Uses scoring service
- Generates and publishes posts
- Adds feedback buttons to published posts
- Keeps scheduler-based autonomous publishing

### `admin_bot.py`

- Runs the admin bot
- Manages topics, sources, keywords, categories
- Generates prompts
- Supports style learning
- Shows stats
- Includes a storefront-like `/start` and `/shop`

### Current risk

`main.py` and `admin_bot.py` still overlap heavily in topic management and prompt-style flows.
This is acceptable for now but is technical debt.

## LLM flow

- `llm_generator.py` contains generation, style extraction, review, and rewrite logic
- It uses RouterAI / DeepSeek-compatible OpenAI API
- The system depends on `ROUTERAI_API_KEY`, `ROUTERAI_BASE_URL`, and `ROUTERAI_MODEL`
- `test_api()` is a startup gate in the bot runtime

## Billing and subscriptions

- Real provider: `YooKassa`
- Manual admin provider: `ManualProvider`
- Stubs: `CloudPaymentsProvider`, `RobokassaProvider`, `TelegramStarsProvider`
- Billing checks are enforced through `BillingService.check_limit(...)`
- Usage counters are persisted in `billing_usage_counters`
- Webhook deduplication is implemented through `billing_webhook_events`
- Publish idempotency is enforced separately in `services/telegram_publish.py`

## Environment

### Required core env

- `BOT_TOKEN`
- `ADMIN_BOT_TOKEN`
- `CHANNEL_ID`
- `ROUTERAI_API_KEY`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

### Billing env

- `BILLING_ENABLED`
- `BILLING_DEFAULT_PROVIDER`
- `YOOKASSA_SHOP_ID`
- `YOOKASSA_SECRET_KEY`
- `YOOKASSA_RETURN_URL`
- `YOOKASSA_WEBHOOK_SECRET`
- `CLOUDPAYMENTS_PUBLIC_ID`
- `CLOUDPAYMENTS_API_SECRET`
- `ROBOKASSA_MERCHANT_LOGIN`
- `ROBOKASSA_PASSWORD_1`
- `ROBOKASSA_PASSWORD_2`
- `TELEGRAM_STARS_ENABLED`

## Commands

### Local start

```bash
pip install -r requirements.txt
python scoring_service.py
python main.py
python admin_bot.py
```

### Unified launcher

```bash
run_bot.bat
```

### API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker-compose up --build
```

## Tests

```bash
pytest -v
pytest -k billing -v
pytest tests/test_topic_profile.py -v
pytest tests/test_source_validation.py -v
pytest tests/test_generation_review.py -v
pytest tests/test_scoring_contract.py -v
```

Smoke test:

```bash
python scripts/smoke_test.py
```

## Known bugs / risks

- Local `.venv` has been unstable in this environment
- RouterAI auth was previously returning `401` until the key was replaced
- `n8n` host addressing depends on whether n8n is local or Dockerized
- `git diff` / `git status` could not be reliably captured in this shell session, so exact uncommitted file state is `UNKNOWN`
- `main.py` and `admin_bot.py` contain duplicated workflows and Russian text mojibake in older parts of the codebase
- `database.py` still creates legacy tables at startup

## Technical debt

- Collapse duplicated topic/admin command handling
- Move startup/runtime concerns out of the bot files
- Tighten the API envelope consistency everywhere
- Remove legacy side effects from `scoring_service.py` if future refactor allows
- Decide whether `main.py` should remain an autonomous polling bot or become a thin publisher

## Do not break

- Topic profile contract
- Billing idempotency
- Telegram publish idempotency
- Backward compatibility of existing bot commands
- Existing asyncpg schema bootstrap until a clean migration path is confirmed
- Separate `8000` API and `8001` scoring service ports

## Recommended next prompt for Codex

> Read `docs/PROJECT_BRIEF.md` and `docs/PROJECT_HANDOFF.md`, then inspect the current runtime logs for `api.log`, `main_bot.log`, `scoring_service.log`, and `admin_bot.log`. Determine which services are actually reachable from n8n in the current local setup, and fix only the startup/runtime wiring if needed. Do not change business logic.

