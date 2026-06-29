# BotTG Project Brief

## What this is

BotTG is a Telegram content automation platform.
It collects source material, scores candidates, generates posts, reviews them, and publishes to Telegram.
The current direction is universal topic support via `topic_profile`, with `n8n` as orchestrator and Python/FastAPI as business logic.

## Who it is for

- Telegram channel owners
- Small editorial teams
- Agencies
- Operators who want scheduled or assisted autoposting

## Main stack

- Python 3.x
- FastAPI
- aiogram 3
- asyncpg + PostgreSQL
- n8n workflows
- OpenAI-compatible RouterAI / DeepSeek stack
- Uvicorn
- APScheduler
- pytest

## Main modules

- `main.py` - main Telegram content bot runtime, fetch/scoring/publish scheduler, feedback handling
- `admin_bot.py` - admin Telegram bot for topic/source/prompt/style management
- `api/main.py` - FastAPI app wiring
- `api/routes/*` - HTTP contracts for topics, sources, scoring, generation, review, telegram publish, billing
- `services/topic_profile.py` - raw topic -> structured topic profile
- `services/source_validation.py` - source URL validation and fetch classification
- `services/scoring.py` - universal scoring contract
- `services/generation.py` - post generation
- `services/review.py` - review and rewrite gate
- `services/telegram_publish.py` - idempotent publish logic
- `services/billing/*` - billing, plans, access checks, limits, providers
- `database.py` - asyncpg schema bootstrap + legacy data helpers
- `parsers.py` - source scrapers
- `scoring_service.py` - separate scoring API on port `8001`

## How to run

Local:

```bash
pip install -r requirements.txt
python scoring_service.py
python main.py
python admin_bot.py
```

Unified launcher:

```bash
run_bot.bat
```

API:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker-compose up --build
```

## How to test

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

## What is already in place

- FastAPI routes for topic profile, source validation, scoring, generation, review, telegram publish, billing
- Billing module with YooKassa provider and manual provider stub
- Billing migration with plans, subscriptions, payments, webhook events, usage counters
- Universal scoring contract with topic-aware weighting
- Generation/review flows that use `topic_profile`
- Idempotent Telegram publish
- n8n workflow templates and single-file orchestrator template
- Main bot and admin bot launch scripts
- Tests for topic profile, source validation, scoring, generation/review, billing

## What is currently in work

- Stabilizing runtime startup on Windows
- Aligning n8n host addressing with the actual API runtime
- Verifying RouterAI auth and API connectivity
- Cleaning up role overlap between `main.py` and `admin_bot.py`

## Next 5 tasks

1. Make one consistent startup path for API + scoring + bots
2. Verify the FastAPI API is reachable from n8n in the actual deployment mode
3. Run the billing and workflow smoke tests end-to-end
4. Reduce duplication between `main.py` and `admin_bot.py`
5. Tighten runtime guards so `billing_enabled=false` remains safe in dev

## Critical constraints

- Do not move business logic into n8n
- Do not replace asyncpg/PostgreSQL with a new ORM stack unless explicitly planned
- Do not break current bot command flows while refactoring
- Do not publish duplicate Telegram posts; idempotency is mandatory
- Do not commit secrets; several credentials were pasted in chat and should be rotated outside the repo
- Do not assume `.venv` is healthy; current local environment has been unstable

## Unknowns

- Exact current git diff: `UNKNOWN` in this shell session
- Exact deployed topology for n8n: `UNKNOWN`
- Whether the active API runs under Docker or local Python: `TODO`

